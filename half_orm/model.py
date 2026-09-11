#!/usr/bin/env python3
#-*- coding: utf-8 -*-

"""Connection to a PostgreSQL database and factory for Relation classes.

:class:`Model` reads connection parameters from a configuration file,
connects to the database, and exposes
:meth:`~half_orm.model.Model.get_relation_class` to generate Python classes
that map to tables and views.

Example:
    Connect to a database and generate a Relation class:

        ```python
        from half_orm.model import Model

        blog = Model('blog')
        Author = blog.get_relation_class('blog.author')
        ```
"""

import importlib
import os
import re
import sys
import threading
import typing
from configparser import ConfigParser
from os import environ

import psycopg
from psycopg import ClientCursor, AsyncConnection
from psycopg.rows import dict_row

from half_orm import model_errors
from half_orm import pg_meta
from half_orm import utils
from half_orm.relation_factory import factory, register_class

CONF_DIR = os.path.abspath(environ.get('HALFORM_CONF_DIR', '/etc/half_orm'))


# UUID is natively supported in psycopg 3

_SQL_TO_JSON = {
    'uuid': 'string', 'text': 'string', 'varchar': 'string', 'bpchar': 'string',
    'int4': 'integer', 'int8': 'integer', 'int2': 'integer',
    'float4': 'number', 'float8': 'number', 'numeric': 'number',
    'bool': 'boolean',
    'date': 'date', 'timestamp': 'datetime', 'timestamptz': 'datetime',
    'jsonb': 'json', 'json': 'json',
}
def _sql_to_json_type(sql_type: str) -> str:
    base = sql_type.lstrip('_')
    return _SQL_TO_JSON.get(base, 'string')

def _config_bool(section, key, default, file_):
    """Read `key` from a connection-file section as a boolean.

    ``ConfigParser`` hands back strings, so a plain truth test on the value
    made ``production = false`` — anything but the exact string ``'False'`` —
    come out *true*. The spellings accepted here are ConfigParser's own:
    true/false, yes/no, on/off, 1/0, in any case.

    Raises:
        MalformedConfigFile: if the value is not a recognizable boolean.
    """
    value = section.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    try:
        return ConfigParser.BOOLEAN_STATES[str(value).strip().lower()]
    except KeyError:
        raise model_errors.MalformedConfigFile(
            file_, f"Invalid boolean value for '{key}'", value) from None


# One segment of a qualified SQL name: a bare identifier, or a double-quoted
# one (embedded quotes doubled, as PostgreSQL spells them).
#   [^\W\d] is a word character that is not a digit — a letter or underscore,
#   Unicode-aware, which is what PostgreSQL accepts to start an identifier.
_NAME_SEGMENT = r'(?:"(?:[^"]|"")+"|[^\W\d][\w$]*)'
_QUALIFIED_NAME_RE = re.compile(rf'^{_NAME_SEGMENT}(?:\.{_NAME_SEGMENT})*$')
_NAME_SEGMENT_RE = re.compile(_NAME_SEGMENT)


def _split_qualified_name(name):
    """Split ``schema.relation`` into its parts, or return None.

    Understands the quoted form, so ``"a""b"."t"`` yields ``['a"b', 't']``.
    Returns None for anything that is not a sequence of quoted or bare
    segments, leaving the caller to fall back on a plain split.
    """
    parts = []
    pos = 0
    while True:
        match = _NAME_SEGMENT_RE.match(name, pos)
        if match is None:
            return None
        segment = match.group(0)
        parts.append(segment[1:-1].replace('""', '"')
                     if segment.startswith('"') else segment)
        pos = match.end()
        if pos == len(name):
            return parts
        if name[pos] != '.':
            return None
        pos += 1


def _check_config_file_name(name):
    """Check `name` designates a file *inside* ``CONF_DIR`` and return it.

    ``Model``'s argument is a connection file *name*, not a path, but it went
    to ``os.path.join(CONF_DIR, name)``, which confines nothing: ``..``
    climbs out, and an absolute path discards ``CONF_DIR`` entirely. That
    matters wherever the name is derived from a request — a multi-tenant
    application picking a connection per tenant — since it decides which
    database, and as which role, the process connects.

    Raises:
        ValueError: if `name` is empty or looks like a path.
    """
    if not isinstance(name, str) or not name:
        raise ValueError(
            f"config_file must be a non-empty string, got {name!r}")
    if name in ('.', '..') or os.sep in name or (os.altsep and os.altsep in name):
        raise ValueError(
            f"config_file must be a file name inside {CONF_DIR}, not a path: {name!r}")
    return name


def _check_qualified_name(name, what):
    """Check `name` is a (possibly schema-qualified) SQL name and return it.

    Function and procedure names are interpolated into the statement — only
    their *arguments* are bound — so a name is the one part of these calls an
    application must not build from untrusted input without checking. A name
    matching this grammar carries no space, parenthesis, semicolon or stray
    quote, and so cannot close the call and start something else.

    The name is returned unchanged rather than re-quoted, so that PostgreSQL
    keeps folding bare identifiers to lower case exactly as before.

    Raises:
        ValueError: if `name` is not a usable SQL name.
    """
    if not isinstance(name, str):
        raise ValueError(f"{what} must be a string, got {type(name).__name__}: {name!r}")
    if not _QUALIFIED_NAME_RE.match(name):
        raise ValueError(
            f"Invalid {what}: {name!r}. Expected a SQL name such as 'my_function' "
            f"or 'my_schema.my_function'.")
    return name


def _check_named_params(kwargs, what):
    """Check that `kwargs` keys are usable as PostgreSQL named arguments.

    They are rendered as ``key => %s``, and ``f(**{'a => 1) --': v})`` is
    legal Python, so the keys need the same treatment as the callable's name.

    Raises:
        ValueError: if a key is not a plain identifier.
    """
    for key in kwargs:
        if not key.isidentifier():
            raise ValueError(
                f"Invalid parameter name for {what}: {key!r}. Named parameters "
                f"must be plain identifiers.")
    return kwargs


def _module_is_absent(exc, module_path):
    """Whether `exc` reports `module_path` missing, not something it imports.

    Both read as ModuleNotFoundError: a relation with no module in the scope
    package is ordinary, while a module whose own imports are broken is a
    defect its author needs to hear about. `exc.name` tells them apart.
    """
    name = getattr(exc, 'name', None)
    if not name:
        return False
    return module_path == name or module_path.startswith(f'{name}.')


def _describe_values(values):
    """Describe query parameters by shape, never by content.

    Query parameters routinely carry passwords, tokens and personal data, so
    a failing query reports what it was given (``(str[19], int, NULL)``)
    rather than the values themselves. Use ``Model.sql_trace = True`` or
    :meth:`~half_orm.relation.Relation.ho_mogrify` to see the interpolated
    query when debugging.
    """
    if values is None:
        return 'none'
    if not isinstance(values, (list, tuple)):
        values = (values,)
    described = []
    for value in values:
        if value is None:
            described.append('NULL')
            continue
        type_name = type(value).__name__
        try:
            described.append(f'{type_name}[{len(value)}]')
        except TypeError:
            described.append(type_name)
    return f"({', '.join(described)})"


def _normalize_with_half_orm_meta(value):
    """Normalize the `with_half_orm_meta` constructor argument.

    Accepts:
        - True / False: expose every / no half_orm_meta.* relation.
        - a comma-separated string, or any other iterable of strings, of
          fully-qualified dotted relation names (e.g.
          "half_orm_meta.identity.user") — an explicit opt-in allowlist.
          Note the schema itself may contain dots (it is everything before
          the LAST dot), but since `classes()`/`desc()` compare against the
          same "schema.relname" join, no split is actually needed here.

    Returns True, False, or a frozenset of dotted names.
    """
    if value is True or value is False:
        return value
    if isinstance(value, str):
        names = {v.strip() for v in value.split(',') if v.strip()}
    else:
        names = {str(v).strip() for v in value if str(v).strip()}
    return frozenset(names) if names else False

register = register_class

class Model:
    """Connection to a PostgreSQL database.

    Args:
        config_file (str): name of the connection file searched in
            ``HALFORM_CONF_DIR`` (env var, defaults to ``/etc/half_orm``).
            File format:
                [database]
                name       = <db name>    # mandatory
                user       = <user>
                password   = <password>
                host       = <host>
                port       = <port>
                production = <bool>       # default: false
                crud_only  = <bool>       # default: false

            ``name`` is the only mandatory key when using peer authentication.
            Booleans accept ``true``/``false``, ``yes``/``no``, ``on``/``off``
            and ``1``/``0``, in any case; anything else raises
            ``MalformedConfigFile``.

            ``production`` records the environment this connection belongs
            to. half_orm itself does not act on it — query parameters are
            never written to the logs, in any mode — but extensions do:
            half_orm_dev makes a server read-only when it is set.

            ``crud_only`` refuses :meth:`execute_query` and
            :meth:`aexecute_query`, leaving only the Relation CRUD methods.
            It is a guard rail against accidents, not a privilege boundary:
            use ``GRANT``/``REVOKE`` to actually restrict what a role can do.
        scope (str | None): package name used to resolve registered subclasses.
        with_half_orm_meta (bool | str | Iterable[str]): controls whether
            "half_orm_meta.*" relations (half_orm_dev's own metadata schemas)
            are exposed through :meth:`classes`/:meth:`desc`. ``False``
            (default): none are exposed. ``True``: all of them are. A
            comma-separated string, or any other iterable of strings, of
            fully-qualified dotted relation names (e.g.
            ``"half_orm_meta.identity.user"``): only those specific
            relations are exposed — an explicit opt-in allowlist. Exposed
            half_orm_meta relations are always returned as a generic
            :meth:`get_relation_class` instance, never imported from a
            generated package module.

    If no file named ``config_file`` is found in ``HALFORM_CONF_DIR``, it is
    used directly as the database name and a peer-authentication connection
    is attempted (no user/password/host/port) — development use only.

    Raises:
        MalformedConfigFile: if ``name`` is missing from the file.
        psycopg.OperationalError: if the database connection fails.
    """
    __deja_vu = {}
    _classes_ = {}
    __sql_trace = False
    def __init__(self, config_file: None, scope: str=None, with_half_orm_meta=False):
        self.__connection_params = {}
        self._production_mode = True
        self.__load_config(config_file)
        self._scope = scope and scope.split('.')[0]
        self.__thread_local = threading.local()
        self.__with_half_orm_meta = _normalize_with_half_orm_meta(with_half_orm_meta)
        self.__schema_generation = 0
        self.__aconn = None
        self.__connect()

    def has_extension(self, name: str) -> bool:
        """True if the PostgreSQL extension `name` is installed on this database.

        Backed by the same per-dbname metadata cache as :meth:`ho_meta`/
        :meth:`desc` (see :class:`~half_orm.pg_meta.PgMeta`) — a single
        query, refreshed on ``reconnect(reload=True)``, not a per-call
        round-trip. Used e.g. by :attr:`~half_orm.field.Field.unaccent` to
        silently no-op (with a warning) instead of failing at query time
        when ``unaccent`` isn't installed — relevant for a database this
        project doesn't fully control (may lack the CREATE privilege
        needed to install it itself).

        Example::

            model = Model('mydb')
            model.has_extension('unaccent')   # True / False
        """
        return self.__pg_meta.has_extension(self.__dbname, name)

    def __load_config(self, config_file):
        """Load the config file

        If no file named **config_file** is found in *HALFORM_CONF_DIR*, it is
        used directly as the database name and a peer-authentication
        connection is attempted (no user/password/host/port) — development
        use only.

        Raises:
            MalformedConfigFile: if the *name* is missing in the **config_file**.
            RuntimeError: If the reconnection is attempted on another database.
        """
        config_file = _check_config_file_name(config_file)
        config = ConfigParser()
        file_ = os.path.join(CONF_DIR, config_file)
        found = bool(config.read([file_]))
        if found:
            try:
                database = config['database']
            except KeyError as exc:
                raise model_errors.MalformedConfigFile(file_, 'Missing section', 'database') from exc
            try:
                dbname = database['name']
            except KeyError as exc:
                raise model_errors.MalformedConfigFile(file_, 'Missing mandatory parameter', 'name') from exc
        else:
            dbname = config_file
            # WARNING: use peer authentication only in development environment
            database = {'user': None, 'password': None, 'host': None, 'port': None, 'devel': True}

        # Checked for both branches. It used to guard only the one above, so
        # reconnecting through a *missing* file skipped it entirely: the Model
        # silently retargeted itself at another database and, with no file to
        # read credentials from, dropped user/password/host to fall back on
        # peer authentication.
        if self.__connection_params and dbname != self.__dbname:
            raise RuntimeError(
                f"Can't reconnect to another database: {dbname} != {self.__dbname}")

        # Nothing above this line touched self, so a rejected reconnect leaves
        # the Model on its current configuration rather than half-way to one
        # it refused.
        # `production` carries no security meaning inside half_orm — query
        # parameters are never logged, in any mode (see _describe_values).
        # It records the environment a connection belongs to, and extensions
        # act on it: half_orm_dev reads it through Model._production_mode to
        # make a server read-only (no migration, no module regeneration).
        self._production_mode = _config_bool(database, 'production', False, file_)
        self._crud_only = _config_bool(database, 'crud_only', False, file_)
        self.__config_file = config_file
        self.__config_file_path = file_
        self.__config_file_found = found
        self.__connection_params.update({
            'dbname': dbname,
            'user': database.get('user'),
            'password': database.get('password'),
            'host': database.get('host'),
            'port': database.get('port'),
            'connect_timeout': database.get('timeout', 3),
        })

    @property
    def _dbinfo(self):
        return self.__connection_params

    def __connect(self, config_file: str=None, reload: bool=False):
        """Setup a new connection to the database.

        The reconnect method is an alias to the ``__connect`` method.

        Parameters:
            config_file (str): If a config_file is provided, the connection is made with the new
                parameters, allowing to change role. The database name must be the same.
            reload (bool): If set to True, reloads the metadata from the database. Usefull if
                the model has changed.
        """
        # Read the new configuration before dropping the working connection:
        # __load_config refuses a file naming another database, and the Model
        # should come out of a refused reconnect exactly as it went in rather
        # than disconnected and unusable.
        if config_file:
            self.__load_config(config_file)
        self.disconnect()
        try:
            conn = psycopg.connect(**self.__connection_params, row_factory=dict_row, autocommit=True)
        except psycopg.OperationalError as exc:
            if self.__config_file_found:
                config_info = f"Configuration file: '{self.__config_file_path}'"
            else:
                config_info = (
                    f"No configuration file found: '{self.__config_file_path}' "
                    f"(using peer authentication with dbname '{self.__config_file}')")
            raise psycopg.OperationalError(f"{exc}\n{config_info}") from exc
        # Register custom type dumpers on this connection
        from half_orm.null import Null, NullDumper, FieldDumper
        from half_orm.field import Field
        from psycopg.types.json import JsonbDumper
        conn.adapters.register_dumper(Null, NullDumper)
        conn.adapters.register_dumper(Field, FieldDumper)
        conn.adapters.register_dumper(dict, JsonbDumper)
        self.__pg_meta = pg_meta.PgMeta(conn, self.__with_half_orm_meta, reload)
        if reload:
            self.__schema_generation += 1
            self._classes_[self._dbname] = {}
            self.__deja_vu[self.__dbname] = self
        self.__thread_local.conn = conn
        self.__thread_local.schema_generation = self.__schema_generation
        if self.__dbname not in self.__class__.__deja_vu:
            self.__deja_vu[self.__dbname] = self

    reconnect = __connect

    def ho_meta(self) -> dict:
        """Return a structured description of all relations visible in the database scope.

        For each relation (table, view, materialized view…) the returned dict maps
        ``'<schema>/<table>'`` keys to a metadata dict with the following structure::

            {
                'schema':      str,          # schema name
                'table':       str,          # relation name
                'kind':        str,          # 'r' table, 'v' view, 'm' matview, 'p' partition
                'pk_fields':   list[str],    # primary-key column names
                'fields': [
                    {
                        'name':        str,   # column name
                        'sql_type':    str,   # PostgreSQL type (e.g. 'text', 'int4')
                        'json_type':   str,   # JSON schema type (e.g. 'string', 'integer')
                        'is_pk':       bool,
                        'not_null':    bool,
                        'has_default': bool,
                    },
                    ...
                ],
                'fk_deps': [              # outgoing foreign keys
                    {
                        'local_fields':  list[str],
                        'remote_schema': str,
                        'remote_table':  str,
                        'remote_fields': list[str],
                    },
                    ...
                ],
                'reverse_fks': [          # incoming foreign keys
                    {
                        'local_fields':  list[str],
                        'remote_schema': str,
                        'remote_table':  str,
                        'remote_fields': list[str],
                        'is_singleton':  bool,
                    },
                    ...
                ],
            }

        Returns:
            dict: mapping ``'<schema>/<table>'`` → metadata dict (see above).

        Example::

            model = Model('halftest')
            meta = model.ho_meta()
            person = meta['actor/person']
            print(person['kind'])        # 'r'
            print(person['pk_fields'])   # ['id']
            for f in person['fields']:
                print(f['name'], f['sql_type'])
        """
        result = {}
        for kind, sfqrn, _ in self.desc():
            dbname, schema, table = sfqrn
            key = f'{schema}/{table}'
            fields_meta = self._fields_metadata(sfqrn)
            fkeys_meta = self._fkeys_metadata(sfqrn)
            pk_fields = self._pkey_constraint(sfqrn)

            fields = []
            for fname, fdata in fields_meta.items():
                fields.append({
                    'name': fname,
                    'sql_type': fdata['fieldtype'],
                    'json_type': _sql_to_json_type(fdata['fieldtype']),  # helper à ajouter
                    'is_pk': bool(fdata.get('pkey')),
                    'not_null': bool(fdata.get('notnull')),
                    'has_default': fdata.get('default_expr') is not None,
                })

            fk_deps, reverse_fks = [], []
            for fk_name, fk_data in fkeys_meta.items():
                ftable_key, ffields, local_fields, upd, del_, is_reverse, is_singleton = fk_data
                _, r_schema, r_table = ftable_key
                entry = {
                    'local_fields': local_fields,
                    'remote_schema': r_schema,
                    'remote_table': r_table,
                    'remote_fields': ffields,
                }
                if is_reverse:
                    entry['is_singleton'] = is_singleton
                    reverse_fks.append(entry)
                else:
                    fk_deps.append(entry)

            result[key] = {
                'schema': schema, 'table': table, 'kind': kind,
                'pk_fields': pk_fields,
                'fields': fields,
                'fk_deps': fk_deps,
                'reverse_fks': reverse_fks,
            }
        return result

    def get_relation_class(self, relation_name: str, fields_aliases: typing.Dict=None): # -> Relation
        """Generate a :class:`~half_orm.relation.Relation` subclass for a table or view.

        Args:
            relation_name (str): fully qualified name ``'schema.relation'``.
            fields_aliases (dict | None): optional mapping of field aliases.

        Returns:
            type: a class inheriting :class:`~half_orm.relation.Relation`.

        Raises:
            MissingSchemaInName: if the schema part is missing from ``relation_name``.
            UnknownRelation: if the relation does not exist in the database.

        Example:
            Generate a Relation class:
                ```python
                Author = blog.get_relation_class('blog.author')

                # Preferred: subclass and register
                @register
                class Author(blog.get_relation_class('blog.author')):
                    Fkeys = {'post_rfk': '_reverse_fkey_blog_post_author_id'}
                ```

        """
        # Not `relation_name.replace('"', '')`: deleting the quotes made
        # `"a""b"."t"` and `ab.t` the same name, so a relation whose name
        # holds one could not be reached -- or reached a different relation
        # that happened to spell the same without it.
        parts = _split_qualified_name(relation_name)
        if parts is None:
            # A name outside the quoted grammar (a dash, say) still splits on
            # its last dot, as it always did.
            parts = relation_name.rsplit('.', 1)
        if len(parts) < 2:
            raise model_errors.MissingSchemaInName(relation_name)
        schema, table = '.'.join(parts[:-1]), parts[-1]
        return factory({'fqrn': (self.__dbname, schema, table), 'model': self.__deja_vu[self.__dbname], 'fields_aliases':fields_aliases})


    @staticmethod
    def _deja_vu(dbname):
        """Returns None if the database hasn't been loaded yet.
        Otherwise, it returns the Model object already loaded.
        The Model object is shared between all_ the relations in the
        database. The Model object is loaded only once for a given database.
        """
        return Model.__deja_vu.get(dbname)

    @property
    def __dbname(self):
        return self.__connection_params['dbname']

    def ping(self):
        """Check if the connection is alive, reconnecting if needed.

        Returns:
            bool: ``True`` if the connection is established.
        """
        try:
            self.execute_query("select 1")
            return True
        except (psycopg.OperationalError, psycopg.InterfaceError):
            try:
                self.__connect()
                self.execute_query("select 1")
            except (psycopg.OperationalError, psycopg.InterfaceError) as exc: #pragma: no cover
                # log reconnection attempt failure
                sys.stderr.write(f'{exc}\n')
                sys.stderr.flush()
            return False

    def disconnect(self):
        """Closes the current thread's connection to the database."""
        conn = getattr(self.__thread_local, 'conn', None)
        if conn is not None and not conn.closed:
            conn.close()
        self.__thread_local.conn = None

    async def aconnect(self):
        """Setup an async connection to the database.

        Must be called explicitly before using any ``ho_a*`` method.
        The sync connection (used for metadata, ``ho_select``, etc.) remains available.

        *New in version 0.18.0.*
        """
        if self.__aconn is not None and not self.__aconn.closed:
            return
        self.__aconn = await AsyncConnection.connect(
            **self.__connection_params, row_factory=dict_row, autocommit=True)
        from half_orm.null import Null, NullDumper, FieldDumper
        from half_orm.field import Field
        from psycopg.types.json import JsonbDumper
        self.__aconn.adapters.register_dumper(Null, NullDumper)
        self.__aconn.adapters.register_dumper(Field, FieldDumper)
        self.__aconn.adapters.register_dumper(dict, JsonbDumper)

    async def adisconnect(self):
        """Closes the async connection to the database.

        *New in version 0.18.0.*
        """
        if self.__aconn is not None and not self.__aconn.closed:
            await self.__aconn.close()
            self.__aconn = None

    @property
    def _aconnection(self):
        """Property. Returns the async psycopg connection attached to the Model object."""
        if self.__aconn is None:
            raise RuntimeError(
                "No async connection. Call 'await model.aconnect()' first.")
        return self.__aconn

    async def _aexecute_query(self, query, values=None):
        """Internal async query executor — no crud_only check. Called by Relation.__aexecute.

        Mirrors _connection's sync auto-reconnect (see that property's
        docstring: "Connection dropped unexpectedly (conn.closed):
        reconnects automatically"). The async connection is only ever
        opened once, explicitly, via aconnect() (a plain property can't
        await a reconnect the way _connection does) — so without this, a
        connection that goes idle-closed between requests (Postgres or an
        intermediate proxy dropping it) breaks every ho_a* call until the
        process restarts. Reconnect proactively if already flagged closed,
        or by reconnecting once and retrying if the drop is only surfaced
        when the query itself is attempted.
        """
        values = self._unwrap_values(values)

        def _log_error():
            # See _execute_query: parameters are described, never disclosed.
            utils.error(
                f"Query execution failed:\nquery: {query}\n"
                f"values: {_describe_values(values)}\n")

        if self.__aconn is not None and self.__aconn.closed:
            await self.aconnect()
        try:
            cursor = self._aconnection.cursor(row_factory=dict_row)
            await cursor.execute(query, values)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            await self.aconnect()
            try:
                cursor = self._aconnection.cursor(row_factory=dict_row)
                await cursor.execute(query, values)
            except psycopg.Error as exc:
                _log_error()
                raise exc
        except psycopg.Error as exc:
            _log_error()
            raise exc
        return cursor

    async def aexecute_query(self, query, values=None):
        """Execute a raw SQL query asynchronously. *Executes SQL.*

        Raises:
            PermissionError: if ``crud_only`` is set in the connection configuration.
        """
        if self._crud_only:
            raise PermissionError(
                "Direct SQL execution is disabled (crud_only = true in connection config).")
        return await self._aexecute_query(query, values)

    def _reload(self, config_file=None):
        """Reload metadata

        Updates the model according to changes made to the database.
        """
        self.__connect(config_file, True)

    @property
    def _dbname(self):
        """
        property. Returns the database name.
        """
        return self.__dbname

    @property
    def _connection(self):
        """\
        Property. Returns the psycopg connection for the current thread.

        - First access from a new thread: opens a connection lazily.
        - Connection dropped unexpectedly (conn.closed): reconnects automatically.
        - After an explicit disconnect(): raises InterfaceError until reconnect()
          is called.
        """
        tl = self.__thread_local
        if not hasattr(tl, 'conn'):
            # New thread — open a connection lazily
            self.__connect()
        elif getattr(tl, 'conn', None) is not None and tl.conn.closed:
            # Connection dropped unexpectedly — reconnect
            self.__connect()
        elif (getattr(tl, 'schema_generation', -1) != self.__schema_generation
              and getattr(tl, 'conn', None) is not None):
            # Schema was reloaded by another thread — get a fresh connection
            tl.conn.close()
            self.__connect()
        conn = tl.conn
        if conn is None:
            raise psycopg.InterfaceError(
                "Connection closed. Call model.reconnect() to re-establish.")
        return conn

    def _fields_metadata(self, sfqrn):
        "Proxy to PgMeta.fields_meta"
        return self.__pg_meta.fields_meta(self.__dbname, sfqrn)

    def _fkeys_metadata(self, sfqrn):
        "Proxy to PgMeta.fkeys_meta"
        return self.__pg_meta.fkeys_meta(self.__dbname, sfqrn)

    def _relation_metadata(self, fqrn):
        "Proxy to PgMeta.relation_meta"
        return self.__pg_meta.relation_meta(self.__dbname, fqrn)

    def _unique_constraints_list(self, fqrn):
        "Proxy to PgMeta._unique_constraints_list"
        return self.__pg_meta._unique_constraints_list(self.__dbname, fqrn)

    def _pkey_constraint(self, fqrn):
        "Proxy to PgMeta._pkey_constraint"
        return self.__pg_meta._pkey_constraint(self.__dbname, fqrn)

    @staticmethod
    def _unwrap_values(values):
        """Unwrap Field objects in query parameters to their inner values.
        Also converts Null sentinel to Python None (which psycopg maps to SQL NULL).
        """
        if values is None:
            return None
        from half_orm.field import Field
        from half_orm.null import Null
        if isinstance(values, (list, tuple)):
            def _unwrap(v):
                # Recursively unwrap nested Field objects (e.g. Relation(col=other.col))
                while isinstance(v, Field):
                    v = v.value
                if isinstance(v, Null):
                    return None
                # Recurse into lists/tuples (e.g. Field objects inside ANY() arrays)
                if isinstance(v, (list, tuple)):
                    unwrapped = [_unwrap(item) for item in v]
                    return list(unwrapped)
                return v
            unwrapped = [_unwrap(v) for v in values]
            return type(values)(unwrapped)
        return values

    def _execute_query(self, query, values=None, mogrify=False):
        """Internal query executor — no crud_only check. Called by Relation.__execute."""
        values = self._unwrap_values(values)
        cursor = self._connection.cursor(row_factory=dict_row)
        try:
            if mogrify or self.sql_trace:
                client_cur = ClientCursor(self._connection)
                print(client_cur.mogrify(query, values))
            cursor.execute(query, values)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            self.ping()
            cursor = self._connection.cursor(row_factory=dict_row)
            cursor.execute(query, values)
        except psycopg.Error as exc:
            # Shapes only: a failing query must never write its parameters —
            # passwords, tokens, personal data — to the logs.
            utils.error(
                f"Query execution failed:\nquery: {query}\n"
                f"values: {_describe_values(values)}\n")
            raise exc
        return cursor

    def execute_query(self, query, values=None, mogrify=False):
        """Execute a raw SQL query. *Executes SQL.*

        Args:
            query (str): SQL query with ``%s`` placeholders.
            values (tuple | None): query parameters.
            mogrify (bool): if ``True``, print the interpolated query before
                executing. Default: ``False``.

        Returns:
            cursor: psycopg cursor positioned on the result set.

        Warning:
            Always use ``%s`` placeholders — never interpolate user input
            directly into the query string.

        Raises:
            PermissionError: if ``crud_only`` is set in the connection configuration.
        """
        if self._crud_only:
            raise PermissionError(
                "Direct SQL execution is disabled (crud_only = true in connection config).")
        return self._execute_query(query, values, mogrify)

    def execute_function(self, fct_name, *args, **kwargs) -> typing.List[tuple]:
        """Call a PostgreSQL function and return its result set. *Executes SQL.*

        Args:
            fct_name (str): fully qualified function name (``'schema.function'``).
            *args: positional parameters.
            **kwargs: named parameters (``name => value`` syntax).

        Returns:
            list[dict]: rows returned by the function.

        Raises:
            RuntimeError: if both ``*args`` and ``**kwargs`` are provided.
            ValueError: if the name or a named parameter is not a SQL
                identifier. The name is interpolated into the statement,
                unlike the arguments, which are bound.
        """
        if bool(args) and bool(kwargs):
            raise RuntimeError("You can't mix args and kwargs with the execute_function method!")
        fct_name = _check_qualified_name(fct_name, 'function name')
        _check_named_params(kwargs, 'execute_function')
        cursor = self._connection.cursor(row_factory=dict_row)
        if kwargs:
            params = ', '.join([f'{key} => %s' for key in kwargs])
            values = tuple(kwargs.values())
        else:
            params = ', '.join(['%s'] * len(args))
            values = args
        cursor.execute(f"SELECT * FROM {fct_name}({params})", values)
        return cursor.fetchall()

    def call_procedure(self, proc_name, *args, **kwargs):
        """Call a PostgreSQL procedure. *Executes SQL.*

        Args:
            proc_name (str): fully qualified procedure name.
            *args: positional parameters.
            **kwargs: named parameters.

        Returns:
            list[dict] | None: rows if the procedure returns a result set,
            otherwise ``None``.

        Raises:
            RuntimeError: if both ``*args`` and ``**kwargs`` are provided.
            ValueError: if the name or a named parameter is not a SQL
                identifier. The name is interpolated into the statement,
                unlike the arguments, which are bound.
        """
        if bool(args) and bool(kwargs):
            raise RuntimeError("You can't mix args and kwargs with the call_procedure method!")
        proc_name = _check_qualified_name(proc_name, 'procedure name')
        _check_named_params(kwargs, 'call_procedure')
        if kwargs:
            params = ', '.join([f'{key} => %s' for key in kwargs])
            values = tuple(kwargs.values())
        else:
            params = ', '.join(['%s' for _ in range(len(args))])
            values = args
        query = f'call {proc_name}({params})'
        cursor = self._connection.cursor(row_factory=dict_row)
        cursor.execute(query, values)
        try:
            return cursor.fetchall()
        except psycopg.ProgrammingError:
            return None

    async def aexecute_function(self, fct_name, *args, **kwargs) -> typing.List[tuple]:
        """Async version of :meth:`execute_function`. *Executes SQL.*

        Args:
            fct_name (str): fully qualified function name (``'schema.function'``).
            *args: positional parameters.
            **kwargs: named parameters (``name => value`` syntax).

        Returns:
            list[dict]: rows returned by the function.

        Raises:
            RuntimeError: if both ``*args`` and ``**kwargs`` are provided.
            ValueError: if the name or a named parameter is not a SQL
                identifier. The name is interpolated into the statement,
                unlike the arguments, which are bound.
        """
        if bool(args) and bool(kwargs):
            raise RuntimeError("You can't mix args and kwargs with the aexecute_function method!")
        fct_name = _check_qualified_name(fct_name, 'function name')
        _check_named_params(kwargs, 'aexecute_function')
        if kwargs:
            params = ', '.join([f'{key} => %s' for key in kwargs])
            values = tuple(kwargs.values())
        else:
            params = ', '.join(['%s'] * len(args))
            values = args
        cursor = await self.aexecute_query(f"SELECT * FROM {fct_name}({params})", values)
        return await cursor.fetchall()

    async def acall_procedure(self, proc_name, *args, **kwargs):
        """Async version of :meth:`call_procedure`. *Executes SQL.*

        Args:
            proc_name (str): fully qualified procedure name.
            *args: positional parameters.
            **kwargs: named parameters.

        Returns:
            list[dict] | None: rows if the procedure returns a result set,
            otherwise ``None``.

        Raises:
            RuntimeError: if both ``*args`` and ``**kwargs`` are provided.
            ValueError: if the name or a named parameter is not a SQL
                identifier. The name is interpolated into the statement,
                unlike the arguments, which are bound.
        """
        if bool(args) and bool(kwargs):
            raise RuntimeError("You can't mix args and kwargs with the acall_procedure method!")
        proc_name = _check_qualified_name(proc_name, 'procedure name')
        _check_named_params(kwargs, 'acall_procedure')
        if kwargs:
            params = ', '.join([f'{key} => %s' for key in kwargs])
            values = tuple(kwargs.values())
        else:
            params = ', '.join(['%s' for _ in range(len(args))])
            values = args
        cursor = await self.aexecute_query(f'call {proc_name}({params})', values)
        try:
            return await cursor.fetchall()
        except psycopg.ProgrammingError:
            return None

    def has_relation(self, qtn: str) -> bool:
        """Return ``True`` if the relation exists in the database.

        Args:
            qtn (str): qualified table name, e.g. ``'public.person'``.

        Returns:
            bool
        """
        return self.__pg_meta.has_relation(self.__dbname, *qtn.rsplit('.', 1))

    def _import_class(self, qtn, scope=None):
        """Return the class for `qtn` from the scope package, if there is one.

        Falls back to a generated class when the scope package has no module
        for this relation.
        """
        self._scope = scope or self._scope
        if not self._scope:
            # The module path is built from the relation's schema and name,
            # which are database data. Without a scope package to root it in,
            # `__import__` would be handed a top-level module name chosen by
            # whoever can create a schema -- and importing a module runs it,
            # which makes that execution, not lookup.
            return self.get_relation_class(qtn)

        plain_qtn = qtn.replace('"', '')
        if not all(part.isidentifier() for part in plain_qtn.split('.')):
            # Nothing importable can be named this; asking would only probe
            # the import system with a name out of the database.
            return self.get_relation_class(qtn)

        module_path = f'{self._scope}.{plain_qtn}'
        _class_name = pg_meta.class_name(qtn)

        try:
            module = __import__(
                module_path, globals(), locals(), [_class_name], 0)
        except ModuleNotFoundError as exc:
            if not _module_is_absent(exc, module_path):
                # The module is there; something it imports is not. Swallowing
                # that removed the caller's own code from the program without
                # a word -- the generated class simply arrived without their
                # methods on it.
                raise
            return self.get_relation_class(qtn)

        try:
            return module.__dict__[_class_name]
        except KeyError:
            return self.get_relation_class(qtn)

    def _relations(self):
        """List all_ the relations in the database"""
        rels = self.__pg_meta.relations_list(self.__dbname)
        return rels

    def desc(self):
        """Returns the list of the relations of the model.

        Each element in the list contains:

        * the relation type: 'r' relation, 'v' view, 'm' materialized view, 'p' partition;
        * a tuple identifying the relation: (db name>, <schema name>, <relation name>);
        * a list of tuples indentifying the inherited relations.

        Example:
            list model relations:
                ```python
                from half_orm.model import Model
                halftest = Model('halftest')
                halftest.desc()

                [('r', ('halftest', 'actor', 'person'), []), ('r', ('halftest', 'blog', 'comment'), []), ('r', ('halftest', 'blog', 'event'), [('halftest', 'blog', 'post')]), ('r', ('halftest', 'blog', 'post'), []), ('v', ('halftest', 'blog.view', 'post_comment'), [])]
                ```

        """
        return self.__pg_meta.desc(self.__dbname)

    def __str__(self):
        return self.__pg_meta.str(self.__dbname)

    def classes(self):
        "Returns the all the classes of the model"
        for relation in self._relations():
            package_name = relation[1][0]
            module_name = ".".join(relation[1][1:])
            if module_name.find('half_orm_meta') == 0:
                allow = self.__with_half_orm_meta
                if allow is True or (allow and module_name in allow):
                    yield self.get_relation_class(module_name), relation[0]
            else:
                # getattr() on the freshly imported module reads the actual
                # (possibly `@register`-ed) class straight from its namespace,
                # regardless of the model._classes_ registry — which reload
                # (reconnect(reload=True)) clears without re-running already
                # imported modules, so get_relation_class() alone could go
                # stale. Fall back to it only when there's no generated
                # package to import from, or its conventional class is missing.
                try:
                    class_name = pg_meta.camel_case(relation[1][-1])
                    module = importlib.import_module(f".{module_name}", package_name)
                    yield getattr(module, class_name), relation[0]
                except (ModuleNotFoundError, AttributeError):
                    yield self.get_relation_class(module_name), relation[0]

    @property
    def sql_trace(self) -> bool:
        """bool: if ``True``, every SQL query is printed to stdout before execution."""
        return self.__sql_trace

    @sql_trace.setter
    def sql_trace(self, value: bool) -> None:
        self.__sql_trace = value
