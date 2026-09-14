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

register = register_class

# One segment of a qualified SQL name: a bare identifier, or a double-quoted
# one (embedded quotes doubled, as PostgreSQL spells them).
#   [^\W\d] is a word character that is not a digit -- a letter or underscore,
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
    matters wherever the name is derived from a request -- a multi-tenant
    application picking a connection per tenant -- since it decides which
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

    Function and procedure names are interpolated into the statement -- only
    their *arguments* are bound -- so a name is the one part of these calls an
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


class Model:
    """Connection to a PostgreSQL database.

    Args:
        config_file (str): name of the connection file searched in
            ``HALFORM_CONF_DIR`` (env var, defaults to ``/etc/half_orm``).
            File format:
                [database]
                name     = <db name>      # mandatory
                user     = <user>
                password = <password>
                host     = <host>
                port     = <port>

            ``name`` is the only mandatory key when using peer authentication.
        scope (str | None): package name used to resolve registered subclasses.

    Raises:
        MissingConfigFile: if the configuration file is not found.
        MalformedConfigFile: if ``name`` is missing from the file.
        psycopg.OperationalError: if the database connection fails.
    """
    __deja_vu = {}
    _classes_ = {}
    __sql_trace = False
    def __init__(self, config_file: None, scope: str=None):
        self._dbinfo = {}
        self._production_mode = True
        self.__load_config(config_file)
        self._scope = scope and scope.split('.')[0]
        self.__thread_local = threading.local()
        self.__schema_generation = 0
        self.__aconn = None
        self.__connect()

    def __load_config(self, config_file):
        """Load the config file

        Raises:
            MissingConfigFile: If the **config_file** is not found in *HALFORM_CONF_DIR*.
            MalformedConfigFile: if the *name* is missing in the **config_file**.
            ValueError: if **config_file** is not a plain file name.
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
        if self._dbinfo and dbname != self.__dbname:
            raise RuntimeError(
                f"Can't reconnect to another database: {dbname} != {self.__dbname}")

        # Nothing above this line touched self, so a rejected reconnect leaves
        # the Model on its current configuration rather than half-way to one
        # it refused.
        production = database.get('production', False)
        if production == 'False': # production = False
            production = False
        self._production_mode = production
        self.__config_file = config_file
        self.__config_file_path = file_
        self.__config_file_found = found
        self._dbinfo.update({
            'dbname': dbname,
            'user': database.get('user'),
            'password': database.get('password'),
            'host': database.get('host'),
            'port': database.get('port'),
            'connect_timeout': database.get('timeout', 3),
        })

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
            conn = psycopg.connect(**self._dbinfo, row_factory=dict_row, autocommit=True)
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
        self.__pg_meta = pg_meta.PgMeta(conn, reload)
        if reload:
            self.__schema_generation += 1
            self._classes_[self._dbname] = {}
        self.__thread_local.conn = conn
        self.__thread_local.schema_generation = self.__schema_generation
        if self.__dbname not in self.__class__.__deja_vu:
            self.__deja_vu[self.__dbname] = self

    reconnect = __connect

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
        return self._dbinfo['dbname']

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
            **self._dbinfo, row_factory=dict_row, autocommit=True)
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

    async def aexecute_query(self, query, values=None):
        """Executes a raw SQL query using the async connection."""
        values = self._unwrap_values(values)
        cursor = self._aconnection.cursor(row_factory=dict_row)
        try:
            await cursor.execute(query, values)
        except psycopg.Error as exc:
            vals = ''
            if not self._production_mode:
                vals = f"values: {values}\n"
            utils.error(f"Query execution failed:\nquery: {query}\n{vals}")
            raise exc
        return cursor

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
        """
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
            vals = ''
            if not self._production_mode:
                # report values only in development mode
                vals = f"values: {values}\n"
            utils.error(f"Query execution failed:\nquery: {query}\n{vals}")
            raise exc
        return cursor

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
        """Used to return the class from the scope module.

        This method is used to import a class from a module. The module
        must reside in an accessible python package named `scope`.
        """
        t_qtn = qtn.replace('"', '').rsplit('.', 1)
        self._scope = scope or self._scope
        module_path = ".".join(t_qtn)
        if self._scope:
            module_path = f'{self._scope}.{module_path}'
        _class_name = pg_meta.class_name(qtn) # XXX
        try:
            module = __import__(
                module_path, globals(), locals(), [_class_name], 0)
            return module.__dict__[_class_name]
        except:
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
                continue
            class_name = pg_meta.camel_case(relation[1][-1])
            module = importlib.import_module(f".{module_name}", package_name)
            yield getattr(module, class_name), relation[0]

    @property
    def sql_trace(self) -> bool:
        """bool: if ``True``, every SQL query is printed to stdout before execution."""
        return self.__sql_trace

    @sql_trace.setter
    def sql_trace(self, value: bool) -> None:
        self.__sql_trace = value
