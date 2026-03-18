#!/usr/bin/env python3
#-*- coding: utf-8 -*-

"""This module provides the class Model.

The class Model is responsible for the connection to the PostgreSQL database.

Once connected, you can use the
`get_relation_class <#half_orm.model.Model.get_relation_class>`_
method to generate a class to access any relation (table/view) in your database.

Example:
    >>> from half_orm.model import Model
    >>> model = Model('my_config_file')
    >>> class MyTable(model.get_relation_class('my_schema.my_table')):
    ...     # Your business code goes here

Note:
    The default schema is ``public`` in PostgreSQL, so to reference a table
    ``my_table`` in this schema you'll have to use ``pubic.my_table``.
"""

import importlib
import os
import sys
import typing
from configparser import ConfigParser
from os import environ

import psycopg
from psycopg import ClientCursor
from psycopg.rows import dict_row

from half_orm import model_errors
from half_orm import pg_meta
from half_orm import utils
from half_orm.relation_factory import factory, register_class

CONF_DIR = os.path.abspath(environ.get('HALFORM_CONF_DIR', '/etc/half_orm'))


# UUID is natively supported in psycopg 3

register = register_class

class Model:
    """
    Parameters:
        config_file (str): the configuration file that contains the informations to connect
            to the database.
        scope (Optional[str]): used to agregate several modules in a package.
            See `hop <https://github.com/half-orm/half-orm/blob/main/doc/hop.md>`_.

    Note:
        The **config_file** is searched in the `HALFORM_CONF_DIR` variable if specified,
        then in `/etc/half_orm`. The file format is as follows:

            | [database]
            | name = <postgres db name>
            | user = <postgres user>
            | password = <postgres password>
            | host = <host name | localhost>
            | port = <port | 5432>

        *name* is the only mandatory entry if you are using an
        `ident login with a local account <https://www.postgresql.org/docs/current/auth-ident.html>`_.
    """
    __deja_vu = {}
    _classes_ = {}
    __sql_trace = False
    def __init__(self, config_file: None, scope: str=None):
        """Model constructor

        Use @config_file in your scripts. The @dbname parameter is
        reserved to the __factory metaclass.
        """
        self._dbinfo = {}
        self._production_mode = True
        self.__load_config(config_file)
        self._scope = scope and scope.split('.')[0]
        self.__conn = None
        self.__connect()

    def __load_config(self, config_file):
        """Load the config file

        Raises:
            MissingConfigFile: If the **config_file** is not found in *HALFORM_CONF_DIR*.
            MalformedConfigFile: if the *name* is missing in the **config_file**.
            RuntimeError: If the reconnection is attempted on another database.
        """
        self.__config_file = config_file
        config = ConfigParser()
        self.__config_file_path = os.path.join(CONF_DIR, self.__config_file)
        file_ = self.__config_file_path
        self.__config_file_found = bool(config.read([file_]))
        if self.__config_file_found:
            try:
                database = config['database']
            except KeyError as exc:
                raise model_errors.MalformedConfigFile(file_, 'Missing section', 'database') from exc
            try:
                dbname = database['name']
            except KeyError as exc:
                raise model_errors.MalformedConfigFile(file_, 'Missing mandatory parameter', 'name') from exc

            if self._dbinfo and dbname != self.__dbname:
                raise RuntimeError(
                    f"Can't reconnect to another database: {dbname} != {self.__dbname}")
            self._dbinfo['dbname'] = dbname

        else:
            dbname = config_file
            self._dbinfo['dbname'] = dbname
            # WARNING: use peer authentication only in development environment
            database = {'user': None, 'password': None, 'host': None, 'port': None, 'devel': True}

        self._dbinfo['user'] = database.get('user')
        self._dbinfo['password'] = database.get('password')
        self._dbinfo['host'] = database.get('host')
        self._dbinfo['port'] = database.get('port')
        self._dbinfo['connect_timeout'] = database.get('timeout', 3)
        self._production_mode = database.get('production', False)
        if self._production_mode == 'False': # production = False
            self._production_mode = False

    def __connect(self, config_file: str=None, reload: bool=False):
        """Setup a new connection to the database.

        The reconnect method is an alias to the ``__connect`` method.

        Parameters:
            config_file (str): If a config_file is provided, the connection is made with the new
                parameters, allowing to change role. The database name must be the same.
            reload (bool): If set to True, reloads the metadata from the database. Usefull if
                the model has changed.
        """
        self.disconnect()

        if config_file:
            self.__load_config(config_file)
        try:
            self.__conn = psycopg.connect(**self._dbinfo, row_factory=dict_row, autocommit=True)
        except psycopg.OperationalError as exc:
            if self.__config_file_found:
                config_info = f"Configuration file: '{self.__config_file_path}'"
            else:
                config_info = (
                    f"No configuration file found: '{self.__config_file_path}' "
                    f"(using peer authentication with dbname '{self.__config_file}')")
            raise psycopg.OperationalError(f"{exc}\n{config_info}") from exc
        # Register custom type dumpers on this connection
        from half_orm.null import Null, NullDumper
        from psycopg.types.json import JsonbDumper
        self.__conn.adapters.register_dumper(Null, NullDumper)
        self.__conn.adapters.register_dumper(dict, JsonbDumper)
        self.__pg_meta = pg_meta.PgMeta(self.__conn, reload)
        if reload:
            self._classes_[self._dbname] = {}
        if self.__dbname not in self.__class__.__deja_vu:
            self.__deja_vu[self.__dbname] = self

    reconnect = __connect

    def get_relation_class(self, relation_name: str, fields_aliases: typing.Dict=None): # -> Relation
        """This method is a factory that generates a class that inherits the `Relation <#half_orm.relation.Relation>`_ class.

        Args:
            relation_name (string): the full name (`<schema>.<relation>`) of the targeted relation in the database.

        Raises:
            ValueError: if the schema is missing in relation_name
            UnknownRelationError: if the relation is not found in the database

        Returns:
            a class that inherits the `Relation <#half_orm.relation.Relation>`_ class:
                the class corresponding to the relation in the database.

        Examples:
            A class inheriting the `Relation <#half_orm.relation.Relation>`_ class is returned:
                >>> Person = model.get_relation_class('actor.person')
                >>> Person
                <class 'half_orm.relation.Table_HalftestActorPerson'>
                >>> Person.__bases__
                (<class 'half_orm.relation.Relation'>,)

            A prefered way to create a class:
                >>> class Person(model.get_relation_class('actor.person)):
                >>>     # Your code goes here

            A `MissingSchemaInName <#half_orm.model_errors.MissingSchemaInName>`_ is raised when the schema name is missing:
                >>> model.get_relation_class('person')
                [...]MissingSchemaInName: do you mean 'public.person'?

            An `UnknownRelation <#half_orm.model_errors.UnknownRelation>`_ is raised if the relation is not found in the model:
                >>> model.get_relation_class('public.person')
                [...]UnknownRelation: 'public.person' does not exist in the database halftest.
        """
        try:
            schema, table = relation_name.replace('"', '').rsplit('.', 1)
        except ValueError as err:
            raise model_errors.MissingSchemaInName(relation_name) from err
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
        """Checks if the connection is still established.
        Attempts a new connection otherwise.

        Returns:
            bool: True if the connection is established, False otherwise.
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
        """Closes the connection to the database.
        """
        if self.__conn is not None and not self.__conn.closed:
            self.__conn.close()

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
        Property. Returns the psycopg connection attached to the Model object.
        """
        return self.__conn

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
                if isinstance(v, Field):
                    v = v.value
                if isinstance(v, Null):
                    return None
                # psycopg 3 needs list (not tuple) for ANY() array params
                if isinstance(v, tuple):
                    return list(v)
                return v
            unwrapped = [_unwrap(v) for v in values]
            return type(values)(unwrapped)
        return values

    def execute_query(self, query, values=None, mogrify=False):
        """Executes a raw SQL query.

        Warning:
            This method calls the psycopg
            `cursor.execute <https://www.psycopg.org/docs/cursor.html?highlight=execute#cursor.execute>`_
            function.
            Please read the psycopg documentation on
            `passing parameters to SQL queries <https://www.psycopg.org/docs/usage.html#query-parameters>`_.
        """
        values = self._unwrap_values(values)
        cursor = self.__conn.cursor(row_factory=dict_row)
        try:
            if mogrify or self.sql_trace:
                client_cur = ClientCursor(self.__conn)
                print(client_cur.mogrify(query, values))
            cursor.execute(query, values)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            self.ping()
            cursor = self.__conn.cursor(row_factory=dict_row)
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
        """`Executes a PostgreSQL function <https://www.postgresql.org/docs/current/sql-syntax-calling-funcs.html>`_.

        Arguments:
            *args: The list of parameters to be passed to the postgresql function.
            **kwargs: The list of named parameters to be passed to the postgresql function.

        Returns:
            List[tuple]: a list of tuples.

        Raises:
            RuntimeError: If you mix ***args** and ****kwargs**.

        Note:
            You can't mix args and kwargs with the execute_function method!
        """
        if bool(args) and bool(kwargs):
            raise RuntimeError("You can't mix args and kwargs with the execute_function method!")
        cursor = self.__conn.cursor(row_factory=dict_row)
        if kwargs:
            params = ', '.join([f'{key} => %s' for key in kwargs])
            values = tuple(kwargs.values())
        else:
            params = ', '.join(['%s'] * len(args))
            values = args
        cursor.execute(f"SELECT * FROM {fct_name}({params})", values)
        return cursor.fetchall()

    def call_procedure(self, proc_name, *args, **kwargs):
        """`Executes a PostgreSQL procedure <https://www.postgresql.org/docs/current/sql-call.html>`_.

        Arguments:
            *args: The list of parameters to be passed to the postgresql function.
            **kwargs: The list of named parameters to be passed to the postgresql function.

        Returns:
            None | List[tuple]: None or a list of tuples.

        Raises:
            RuntimeError: If you mix ***args** and ****kwargs**.

        Note:
            You can't mix args and kwargs with the call_procedure method!
        """
        if bool(args) and bool(kwargs):
            raise RuntimeError("You can't mix args and kwargs with the call_procedure method!")
        if kwargs:
            params = ', '.join([f'{key} => %s' for key in kwargs])
            values = tuple(kwargs.values())
        else:
            params = ', '.join(['%s' for _ in range(len(args))])
            values = args
        query = f'call {proc_name}({params})'
        cursor = self.__conn.cursor(row_factory=dict_row)
        cursor.execute(query, values)
        try:
            return cursor.fetchall()
        except psycopg.ProgrammingError:
            return None

    def has_relation(self, qtn: str) -> bool:
        """Checks if the qtn is a relation in the database

        Returns:
            bool: True if the relation exists in the database, False otherwise.

        Example:
            >>> model.has_relation('public.person')
            False
            >>> model.has_relation('actor.person')
            True
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
            >>> from half_orm.model import Model
            >>> halftest = Model('halftest')
            >>> halftest.desc()
            [('r', ('halftest', 'actor', 'person'), []), ('r', ('halftest', 'blog', 'comment'), []), ('r', ('halftest', 'blog', 'event'), [('halftest', 'blog', 'post')]), ('r', ('halftest', 'blog', 'post'), []), ('v', ('halftest', 'blog.view', 'post_comment'), [])]
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
        return self.__sql_trace
    @sql_trace.setter
    def sql_trace(self, value: bool) -> None:
        """Sets the value of self.__sql_trace

        If True, all sql queries are displayed on stdout.
        """
        self.__sql_trace = value
