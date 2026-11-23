"""This module provides the SQL query to extract the metadata of a PostgreSQL
database. The query extracts information about tables, views, materialized
views, foreign tables, and partitioned tables along with their columns,
data types, constraints, inheritance hierarchy, and other related information.

The module provides several helper functions to format the results of the
query. These include functions to normalize fully qualified relation names,
convert relation names to CamelCase, and strip double quotes from relation
names.

Functions:

    * strip_quotes(qrn): Removes all double quotes from the given fully qualified
      relation name (fqrn).
    * __get_qrn(fqrn): Returns the qualified relation name (<schema>.<relation>)
      from the given fully qualified relation name (fqrn).
    * normalize_fqrn(t_fqrn): Transforms the tuple (<db name>, <schema name>, <table name>)
      to "<db name>":"<schema name>"."<table name>". Dots are allowed only in the schema name.
    * normalize_qrn(t_qrn): Returns "<schema name>"."<relation name>" for the given qualified
      relation name (qrn) tuple. A schema name can have any number of dots in it, and a table
      name can't have a dot in it.
    * camel_case(string): Returns the given string transformed to camel case.
    * class_name(qrn): Returns the class name from the given qualified relation name (qrn).

The main query is defined as a string variable named _REQUEST. It includes joins
between several PostgreSQL system tables and views to extract the metadata.
The resulting query returns data about tables, views, materialized views, foreign
tables, and partitioned tables in the database, along with information about their
columns and constraints.

Note that this module requires the psycopg library to be installed.
"""

from collections import OrderedDict
from psycopg.rows import dict_row

from half_orm import naming as _naming
from half_orm.model_errors import NamingError, NamingProblem

REL_CLASS_NAMES = {
    'r': 'Table',
    'p': 'Partioned table',
    'v': 'View',
    'm': 'Materialized view',
    'f': 'Foreign data'}

def strip_quotes(qrn):
    "Removes all double quotes from the qrn/fqrn"
    return qrn.replace('"', '')

def __get_qrn(fqrn: tuple) -> tuple:
    "Returns the qualified relation name <schema>.<relation> from the fully qualified relation name"
    return fqrn[1:]

def quote_ident(name) -> str:
    """Quote one SQL identifier, escaping the quotes it contains.

    PostgreSQL allows a quote in a relation name -- `create table "t""bl"` --
    and these names end up interpolated into statements, where an unescaped
    one closes the identifier early.
    """
    return '"' + str(name).replace('"', '""') + '"'

def unquote_ident(name) -> str:
    """Undo quote_ident; a bare name is returned unchanged.

    Only a fully quoted name is unwrapped: `first_name"` is not one, and
    comes back as it went in.
    """
    name = str(name)
    if len(name) >= 2 and name.startswith('"') and name.endswith('"'):
        return name[1:-1].replace('""', '"')
    return name

def _dotted(table_key) -> str:
    "`schema.relation`, as it is written without quotes."
    return f'{table_key[1]}.{table_key[2]}'

def normalize_fqrn(t_fqrn: tuple) -> str:
    """
    Transform the tuple (<db name>, <schema name>, <table name>) in
    "<db name>":"<schema name>"."<table name>".
    Dots are allowed only in the schema name.
    """
    dbname, schemaname, tablename = t_fqrn
    return f'{quote_ident(dbname)}:{quote_ident(schemaname)}.{quote_ident(tablename)}'

def normalize_qrn(t_fqrn):
    """Return "<schema name>"."<relation name>" for a *fully* qualified name.

    Takes the (<db name>, <schema name>, <relation name>) tuple and drops the
    database part -- despite the name, which every caller reads past. A schema
    name may hold any number of dots; a relation name may not.
    """
    return '.'.join([quote_ident(elt) for elt in __get_qrn(t_fqrn)])

def camel_case(string):
    "Retruns the string transformed to camel case"
    ccname = []
    name = string.lower()
    capitalize = True
    for char in name:
        if not char.isalnum():
            capitalize = True
            continue
        if capitalize:
            ccname.append(char.upper())
            capitalize = False
            continue
        ccname.append(char)
    return ''.join(ccname)

def class_name(qrn):
    "Returns the class name from qrn"
    return camel_case(qrn.replace('"', '').split('.')[-1])

_REQUEST = """
SELECT
    a.attrelid AS tableid,
    array_agg( distinct i.inhseqno::TEXT || ':' || i.inhparent::TEXT ) AS inherits,
    c.relkind AS tablekind,
    n.nspname AS schemaname,
    c.relname AS relationname,
    tdesc.description AS tabledescription,
    a.attname AS fieldname,
    a.attnum AS fieldnum,
    adesc.description AS fielddescription,
    a.attndims AS fielddim,
    pt.typname AS fieldtype,
    NOT( a.attislocal ) AS inherited,
    cn_uniq.contype AS uniq,
    cn_uniq.conkey as pkeynum,
    a.attnotnull OR NULL AS notnull,
    cn_pk.contype AS pkey,
    cn_fk.contype AS fkey,
    cn_fk.conname AS fkeyname,
    cn_fk.conkey AS lfkeynum,
    cn_fk.confrelid AS fkeytableid,
    cn_fk.confkey AS fkeynum,
    cn_fk.confupdtype as fkey_confupdtype,
    cn_fk.confdeltype as fkey_confdeltype,
    cdesc.description AS fkeydescription,
    pg_get_expr(d.adbin, d.adrelid) AS default_expr
FROM
    pg_class c -- table
    -- classoid: an oid is unique within its catalog only, so without it the
    -- comment of some other kind of object could be read as this one's.
    LEFT JOIN pg_description tdesc ON
    tdesc.objoid = c.oid AND
    tdesc.classoid = 'pg_class'::regclass AND
    tdesc.objsubid = 0
    LEFT JOIN pg_namespace n ON
    n.oid = c.relnamespace
    LEFT JOIN pg_inherits i ON
    i.inhrelid = c.oid
    LEFT JOIN pg_attribute a ON
    a.attrelid = c.oid
    LEFT JOIN pg_description adesc ON
    adesc.objoid = c.oid AND
    adesc.classoid = 'pg_class'::regclass AND
    adesc.objsubid = a.attnum
    JOIN pg_type pt ON
    a.atttypid = pt.oid
    LEFT JOIN pg_attrdef d ON
    d.adrelid = a.attrelid AND
    d.adnum = a.attnum
    LEFT JOIN pg_constraint cn_uniq ON
    cn_uniq.contype = 'u' AND
    cn_uniq.conrelid = a.attrelid AND
    a.attnum = ANY( cn_uniq.conkey )
    LEFT JOIN pg_constraint cn_pk ON
    cn_pk.contype = 'p' AND
    cn_pk.conrelid = a.attrelid AND
    a.attnum = ANY( cn_pk.conkey )
    LEFT JOIN pg_constraint cn_fk ON
    cn_fk.contype = 'f' AND
    cn_fk.conrelid = a.attrelid AND
    a.attnum = ANY( cn_fk.conkey )
    LEFT JOIN pg_description cdesc ON
    cdesc.objoid = cn_fk.oid AND
    cdesc.classoid = 'pg_constraint'::regclass AND
    cdesc.objsubid = 0
WHERE
    n.nspname <> 'pg_catalog'::name AND
    n.nspname <> 'information_schema'::name AND
    ( c.relkind = 'r'::"char" -- table
      OR c.relkind = 'v'::"char" -- view
      OR c.relkind = 'm' -- materialized view
      OR c.relkind = 'f' -- foreign table/view/mat. view
      OR c.relkind = 'p' -- patitioned table
    ) AND
    a.attnum > 0 -- AND
    AND (i.inhparent is null or i.inhparent not in (select oid from pg_class where relkind = 'p'))
    AND (cn_fk is null or cn_fk.confrelid not in (select inhrelid from pg_inherits where inhparent in (select oid from pg_class where relkind = 'p')))
GROUP BY
    a.attrelid,
    n.nspname,
    c.relname,
    tdesc.description,
    c.relkind,
    a.attnum,
    a.attname,
    a.attnum,
    adesc.description,
    a.attndims,
    a.attislocal,
    pt.typname,
    cn_uniq.contype,
    cn_uniq.conkey,
    a.attnotnull,
    cn_pk.contype,
    cn_fk.contype,
    cn_fk.conname,
    cn_fk.conkey,
    cn_fk.confrelid,
    cn_fk.confkey,
    cn_fk.confupdtype,
    cn_fk.confdeltype,
    cdesc.description,
    d.adbin,
    d.adrelid
ORDER BY
    n.nspname, c.relname, a.attnum
"""

class _Meta(dict):
    __d_meta = {}

    # Keyed by (host, port, dbname), not by dbname alone: two servers may
    # each hold a database of the same name, and answering one with the
    # catalog of the other describes relations it does not have.
    @classmethod
    def deja_vu(cls, key):
        return key in cls.__d_meta

    @classmethod
    def register(cls, key, meta):
        cls.__d_meta[key] = meta

    @classmethod
    def forget(cls, key):
        cls.__d_meta.pop(key, None)

    def __getitem__(self, key):
        return _Meta.__d_meta.__getitem__(key)

class PgMeta:
    """A utility class for loading and storing metadata of a PostgreSQL database.

    Attributes:
        meta (_Meta): A singleton instance of the `_Meta` class.
    """
    meta = _Meta()
    def __init__(self, connection, with_half_orm_meta, reload=False,
                 naming=_naming.NO_NAMING):
        """Initializes a new instance of the `PgMeta` class.

        Args:
            connection (psycopg.extensions.connection): A connection object to a PostgreSQL database.
            with_half_orm_meta (bool | frozenset[str]): already-normalized value
                from Model — True (expose all half_orm_meta.* relations),
                False (expose none), or a frozenset of allowed
                "schema.relname" dotted names (opt-in allowlist).
            reload (bool, optional): A flag indicating whether to reload the metadata from the database. \
            Defaults to False.
            naming (half_orm.naming.Naming): the names declared on the Model,
                and the relations it ignores.

        Raises:
            NamingError: if names derived from the catalog collide.
        """
        info = connection.info
        self.__dbname = info.get_parameters()['dbname']
        # What the connection actually reached, rather than what the
        # configuration asked for: an omitted host or port is resolved by
        # libpq from the environment, and only the result tells two servers
        # apart.
        # The declarations are part of the key: they decide which relations
        # exist and what their attributes are called, so two Models that do
        # not declare the same thing do not share a description.
        self.__naming = naming
        self.__key = (info.host, info.port, self.__dbname, naming)
        self.__with_half_orm_meta = with_half_orm_meta
        if not PgMeta.meta.deja_vu(self.__key) or reload:
            self.__load_metadata(connection)

    def __meta_allowed(self, schema, relname):
        """True if this half_orm_meta.* relation should be exposed by desc()."""
        allow = self.__with_half_orm_meta
        if allow is True:
            return True
        if not allow:
            return False
        return f'{schema}.{relname}' in allow

    def metadata(self, dbname):
        """Retrieves the metadata of the database this instance was built on.

        Args:
            dbname (str): The name of the PostgreSQL database. Kept for the
                signature every accessor here shares; the lookup goes
                through the server the connection reached, since a name
                alone does not identify a database.

        Returns:
            dict: The metadata of the database.
        """
        return self.meta[self.__key]

    def relations_list(self, dbname):
        """Retrieves a list of relations for the specified database.

        Args:
            dbname (str): The name of the PostgreSQL database.

        Returns:
            list: A list of relations for the specified database.
        """
        return self.metadata(dbname)['relations_list']

    def __load_metadata(self, connection):
        """Loads the metadata by querying the PostgreSQL database and registers it in the _Meta singleton.

        Args:
            connection (psycopg.extensions.connection): A connection object to a PostgreSQL database.

        Raises:
            NamingError: if two things end up under one name. Nothing is
                registered then: a description that has silently dropped a
                foreign key or a column is not one to work from.
        """
        naming = self.__naming
        problems = []
        declared_fields = dict(naming.fields)
        declared_reverse = dict(naming.reverse)
        used_declarations = set()

        metadata = {'relations_list': []}
        byname = metadata['byname'] = OrderedDict()
        byid = metadata['byid'] = {}
        with connection.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT extname FROM pg_extension')
            metadata['extensions'] = frozenset(row['extname'] for row in cur.fetchall())
        with connection.cursor(row_factory=dict_row) as cur:
            cur.execute(_REQUEST)
            all_ = [elt for elt in cur.fetchall()
                    if not _naming.is_ignored(
                        naming, elt['schemaname'], elt['relationname'])]
            for dct in all_:
                table_key = (self.__dbname, dct['schemaname'], dct['relationname'])
                tableid = dct['tableid']
                description = dct['tabledescription']
                if table_key not in byname:
                    byid[tableid] = {}
                    byid[tableid]['sfqrn'] = table_key
                    byid[tableid]['fields'] = OrderedDict()
                    byid[tableid]['fkeys'] = OrderedDict()
                    byname[table_key] = OrderedDict()
                    byname[table_key]['description'] = description
                    byname[table_key]['fields'] = OrderedDict()
                    byname[table_key]['fkeys'] = OrderedDict()
                    byname[table_key]['fields_by_num'] = OrderedDict()
            for dct in all_:
                tableid = dct['tableid']
                table_key = byid[tableid]['sfqrn']
                dotted = _dotted(table_key)
                fieldname = dct.pop('fieldname')
                fieldnum = dct['fieldnum']
                tablekind = dct.pop('tablekind')
                # An ignored parent is not in `byid`.
                inherits = [byid[int(elt.split(':')[1])]['sfqrn']
                            for elt in dct.pop('inherits')
                            if elt is not None and int(elt.split(':')[1]) in byid]
                # The name the column is reached through, when one was
                # declared: on the Model first, in its comment otherwise.
                declaration = (dotted, fieldname)
                if declaration in declared_fields:
                    used_declarations.add(('field', declaration))
                    dct['ho_name'] = declared_fields[declaration]
                else:
                    dct['ho_name'] = _naming.annotation(
                        dct['fielddescription'], _naming.FIELD_ANNOTATION)
                byname[table_key]['tableid'] = tableid
                byname[table_key]['tablekind'] = tablekind
                byname[table_key]['inherits'] = inherits
                byname[table_key]['fields'][fieldname] = dct
                byname[table_key]['fields_by_num'][fieldnum] = dct
                byid[tableid]['fields'][fieldnum] = fieldname
                if (tablekind, table_key) not in metadata['relations_list']:
                    metadata['relations_list'].append((tablekind, table_key))
            # (relation, foreign key name) -> what is filed under it. A name
            # with more than one entry is a foreign key that would have
            # replaced another.
            fkey_owners = {}
            # The keys of fkey_owners under which a declared reverse name is
            # filed.
            declared_owners = set()
            seen_constraints = set()
            for dct in all_:
                tableid = dct['tableid']
                table_key = byid[tableid]['sfqrn']
                dotted = _dotted(table_key)
                fkeyname = dct['fkeyname']
                if not fkeyname or (table_key, fkeyname) in seen_constraints:
                    continue
                seen_constraints.add((table_key, fkeyname))
                fkeytableid = dct['fkeytableid']
                if fkeytableid not in byid:
                    # It references an ignored relation: nowhere to go.
                    continue
                ftable_key = byid[fkeytableid]['sfqrn']
                fields = [byid[tableid]['fields'][num] for num in dct['lfkeynum']]
                confupdtype = dct['fkey_confupdtype']
                confdeltype = dct['fkey_confdeltype']
                ffields = [byid[fkeytableid]['fields'][num] for num in dct['fkeynum']]
                declaration = (dotted, fkeyname)
                if declaration in declared_reverse:
                    used_declarations.add(('reverse', declaration))
                    declared = declared_reverse[declaration]
                    origin = 'Model(reverse_names=...)'
                else:
                    declared = _naming.annotation(
                        dct['fkeydescription'], _naming.REVERSE_ANNOTATION)
                    origin = "'@ho_reverse_name' in its comment"
                if declared is not None and not _naming.is_python_name(declared):
                    problems.append(NamingProblem(
                        'declaration', declared, dotted,
                        [f"reverse name declared for the constraint '{fkeyname}'"],
                        f'a reverse name must be written after a dot, and this '
                        f'one is {_naming.python_name_problem(declared)}'))
                    declared = None
                rev_fkey_name = _naming.reverse_fkey_name(table_key, fields, declared)
                fkey_owners.setdefault((table_key, fkeyname), []).append(
                    f"the constraint '{fkeyname}' of {dotted}")
                byname[table_key]['fkeys'].setdefault(fkeyname, (
                    ftable_key, ffields, fields, confupdtype, confdeltype, False, False))
                # Detect one-to-one: FK fields form a UNIQUE or PK on table_key
                target = frozenset(fields)
                pk_fields = frozenset(
                    fname for fname, fd in byname[table_key]['fields'].items()
                    if fd.get('pkey')
                )
                is_singleton = (target == pk_fields)
                if not is_singleton:
                    seen_ugroups = set()
                    for fd in byname[table_key]['fields'].values():
                        if fd.get('uniq'):
                            group = frozenset(
                                byid[tableid]['fields'][num]
                                for num in fd['pkeynum']
                            )
                            if group not in seen_ugroups:
                                seen_ugroups.add(group)
                                if target == group:
                                    is_singleton = True
                                    break
                owner = f"{dotted}({', '.join(fields)}), constraint '{fkeyname}'"
                if declared is not None:
                    # The name is not the derived one: say who chose it, the
                    # fix is then to choose differently, not to name it.
                    owner += f", named by {origin}"
                    declared_owners.add((ftable_key, rev_fkey_name))
                fkey_owners.setdefault((ftable_key, rev_fkey_name), []).append(owner)
                # setdefault, not assignment: the second foreign key to spell
                # this name used to take the place of the first.
                byname[ftable_key]['fkeys'].setdefault(rev_fkey_name, (
                    table_key, fields, ffields, confupdtype, confdeltype, True, is_singleton))

        metadata['relations_list'].sort()
        # 'schema.relation' as it is written without quotes -> the relations
        # spelled that way. A schema may hold dots and so may a relation, so
        # the string alone does not say where one ends and the other starts;
        # the catalog does.
        bydotted = metadata['bydotted'] = {}
        for table_key in byname:
            bydotted.setdefault(_dotted(table_key), []).append(table_key)

        problems += self.__naming_problems(
            byname, bydotted, fkey_owners, declared_owners,
            declared_fields, declared_reverse, used_declarations)
        if problems:
            # Including on a reload: the description read before the schema
            # changed is not one to go on working from, for this Model or
            # for the next one opened on the same database.
            PgMeta.meta.forget(self.__key)
            raise NamingError(self.__dbname, problems)
        PgMeta.meta.register(self.__key, metadata)

    @staticmethod
    def __naming_problems(byname, bydotted, fkey_owners, declared_owners,
                          declared_fields, declared_reverse, used_declarations):
        """Everything that keeps the names of this catalog from being used.

        All of it, not the first: the list is what the user works from, and
        one problem per run is one run per problem.
        """
        problems = []

        # Two relations that read the same once the quotes are gone.
        for dotted, table_keys in bydotted.items():
            if len(table_keys) > 1:
                problems.append(NamingProblem(
                    'qualified_name', dotted, None,
                    [normalize_qrn(table_key) for table_key in table_keys],
                    'rename one of them, or leave one out with `ignore`'))

        # Two foreign keys filed under one name on the same relation.
        for (table_key, name), owners in fkey_owners.items():
            if len(owners) > 1:
                if (table_key, name) in declared_owners:
                    hint = ("this name was declared: declare a different one "
                            "for each foreign key. ")
                else:
                    hint = "name one of them: "
                problems.append(NamingProblem(
                    'reverse_fkey', name, _dotted(table_key), owners,
                    hint + "COMMENT ON CONSTRAINT <constraint> ON "
                    "<relation> IS '@ho_reverse_name <name>', or "
                    "Model(reverse_names={('<relation>', '<constraint>'): '<name>'})"))

        for table_key, relation in byname.items():
            dotted = _dotted(table_key)
            attributes = {}
            for column, field in relation['fields'].items():
                declared = field.get('ho_name')
                if declared is not None and not _naming.is_python_name(declared):
                    problems.append(NamingProblem(
                        'declaration', declared, dotted,
                        [f"name declared for the column '{column}'"],
                        f'a column name must be written after a dot, and this '
                        f'one is {_naming.python_name_problem(declared)}'))
                    declared = field['ho_name'] = None
                py_name = _naming.python_field_name(
                    column, field['fieldnum'], declared)
                if _naming.is_reserved(py_name):
                    problems.append(NamingProblem(
                        'reserved', py_name, dotted, [f"column '{column}'"],
                        "half_orm uses this name itself. Give the column "
                        f"another one: COMMENT ON COLUMN {normalize_qrn(table_key)}"
                        f".{quote_ident(column)} IS '@ho_name <name>', or "
                        f"Model(field_names={{{dotted!r}: {{{column!r}: '<name>'}}}})"))
                    continue
                attributes.setdefault(py_name, []).append(f"column '{column}'")
            for fkey_name, fkey in relation['fkeys'].items():
                what = 'reverse foreign key' if fkey[5] else 'foreign key'
                attributes.setdefault(
                    _naming.fkey_attribute(fkey_name), []).append(
                        f"{what} '{fkey_name}'")
            for attribute, members in attributes.items():
                if len(members) > 1:
                    problems.append(NamingProblem(
                        'attribute', attribute, dotted, members,
                        "give the column another name ('@ho_name' in its "
                        "comment, or Model(field_names=...)), or rename the "
                        "constraint"))

        # A declaration that names nothing is a typo, and a typo here leaves
        # in place the very clash it was written to settle.
        for (relation, column) in declared_fields:
            if ('field', (relation, column)) not in used_declarations:
                problems.append(NamingProblem(
                    'declaration', declared_fields[(relation, column)], relation,
                    [f"field_names names the column '{column}'"],
                    'no such column on a relation of this model'))
        for (relation, constraint) in declared_reverse:
            if ('reverse', (relation, constraint)) not in used_declarations:
                problems.append(NamingProblem(
                    'declaration', declared_reverse[(relation, constraint)], relation,
                    [f"reverse_names names the constraint '{constraint}'"],
                    'no such foreign key on a relation of this model'))
        return problems

    def resolve(self, dbname, name):
        """Find the relation an unquoted `schema.relation` string designates.

        Returns ``(schema, relation)`` when exactly one relation of the
        database is spelled that way, None otherwise -- no such relation, or
        a name that needs quotes to be told apart from another.
        """
        found = self.metadata(dbname)['bydotted'].get(name, ())
        if len(found) == 1:
            return found[0][1], found[0][2]
        return None

    def has_relation(self, dbname, schema, relation):
        """Checks whether the specified relation exists in the specified database.

        Args:
            dbname (str): The name of the PostgreSQL database.
            schema (str): The name of the schema containing the relation.
            relation (str): The name of the relation.

        Returns:
            bool: True if the relation exists, False otherwise.
        """
        return (dbname, schema, relation) in self.metadata(dbname)['byname']

    def has_extension(self, dbname, name):
        """Checks whether the specified PostgreSQL extension is installed.

        Args:
            dbname (str): The name of the PostgreSQL database.
            name (str): The extension name (e.g. "unaccent").

        Returns:
            bool: True if the extension is installed, False otherwise.
        """
        return name in self.metadata(dbname)['extensions']


    def desc(self, dbname):
        """Returns a list of relations for the specified database.

        Args:
            dbname (str): The name of the PostgreSQL database.

        Returns:
            list: A list of relations for the specified database, with each item containing:
                - The relation type ('r' for table, 'v' for view, or 'm' for materialized view).
                - The fully qualified relation name (FQRN) in the format\
                "<database name>:<schema name>.<relation name>".
                - A list of the FQRN of the inherited relations.
        """
        ret_val = []
        entry = self.metadata(dbname)['byname']
        for key in entry:
            if key[1].find('half_orm_meta') == 0 and not self.__meta_allowed(key[1], key[2]):
                continue
            inh = []
            tablekind = entry[key]['tablekind']
            if entry[key]['inherits']:
                inh = [elt for elt in entry[key]['inherits']]
            ret_val.append((tablekind, key, inh))
        return ret_val

    def fields_meta(self, dbname, sfqrn):
        """Retrieves the metadata of the fields for the specified fully qualified relation name (FQRN).

        Args:
            dbname (str): The name of the PostgreSQL database.
            sfqrn (str): The fully qualified relation name (FQRN) in the format \
            "<schema name>.<relation name>".

        Returns:
            dict: The metadata of the fields for the specified relation.
        """
        return self.metadata(dbname)['byname'][sfqrn]['fields']

    def fkeys_meta(self, dbname, sfqrn):
        """
        Returns the foreign keys metadata for a given sfqrn.

        Args:
            dbname (str): The name of the database.
            sfqrn (str): The fully qualified relation name for the table whose foreign key metadata you want.

        Returns:
            dict: A dictionary containing metadata about the foreign keys for the given table.
        """
        return self.metadata(dbname)['byname'][sfqrn]['fkeys']

    def relation_meta(self, dbname, fqrn):
        """
        Returns the relation metadata for a given fqrn.

        Args:
            dbname (str): The name of the database.
            fqrn (str): The fully qualified relation name for the table whose metadata you want.

        Returns:
            dict: A dictionary containing metadata about the given table.
        """
        return self.metadata(dbname)['byname'][fqrn]

    def str(self, dbname, with_hop_meta=False):
        """
        Returns a string representation of the metadata for all tables in the given database.
        Args:
            dbname (str): The name of the database.
            with_hop_meta (bool): Include half_orm_meta tables in output
        Returns:
            str: A string containing metadata about all tables in the given database.
        """
        relations = []
        max_entry_len = 0
        entry = self.metadata(dbname)['byname']
        
        
        for key in entry:
            # Skip half_orm_meta tables unless explicitly requested
            if not with_hop_meta and key[1].startswith('half_orm_meta'):
                continue
                
            relname = f"{entry[key]['tablekind']} {normalize_qrn(key)}"
            max_entry_len = max(len(relname), max_entry_len)
            
            # Handle missing descriptions gracefully
            description = entry[key].get('description', 'No description available')
            if description:
                description = description.split('\n')[0].strip()
            if not description:
                description = 'No description available'
                
            relations.append((relname, description))
        
        # Sort relations by type then name for better organization
        relations.sort(key=lambda x: (x[0].split()[0], x[0]))
        
        # Build the formatted output
        rel_list = '\n'.join([
            f"{rel:<{max_entry_len + 1}} → {description}" 
            for rel, description in relations
        ])
        
        rel_list = f"📋 Available relations for {dbname}:\n{rel_list}"

        # Add legend if there are relations
        if relations:
            rel_list += '\n\n📋 Relation Types:'
            for key, value in REL_CLASS_NAMES.items():
                rel_list += f"\n  {key}: {value}"
        else:
            rel_list += "No relations found in this database."
        
        return rel_list

    def _unique_constraints_list(self, dbname, sfqrn):
        """
        Returns the unique constraints of the given sfqrn.

        Args:
            dbname (str): The name of the database.
            sfqrn (str): The fully qualified relation name for the table whose unique constraints you want.

        Returns:
            list: A list of tuples, where each tuple contains the names of the fields that make up a unique constraint.
        """
        rel_meta_by_name = self.metadata(dbname)['byname'][sfqrn]
        tableid = rel_meta_by_name['tableid']
        rel_meta_by_id = self.metadata(dbname)['byid']
        unique_by_num = []
        for key, value in rel_meta_by_name['fields'].items():
            if value['uniq']:
                t_uniq = tuple(value['pkeynum'])
                if unique_by_num.count(t_uniq) == 0:
                    unique_by_num.append(t_uniq)
        unique = []
        for elt in unique_by_num:
            fields_names = []
            for num in elt:
                fields_names.append(rel_meta_by_id[tableid]['fields'][num])
            unique.append(tuple(fields_names))
        return unique

    def _pkey_constraint(self, dbname, sfqrn):
        """Returns the primary key constraint for the given sfqrn.

        Args:
            dbname (str): The name of the database.
            sfqrn (str): The fully qualified relation name for the table whose primary key constraint you want.

        Returns:
            list: A list of the names of the fields that make up the primary key constraint.
        """
        rel_meta_by_name = self.metadata(dbname)['byname'][sfqrn]
        tableid = rel_meta_by_name['tableid']
        rel_meta_by_id = self.metadata(dbname)['byid']
        pkey_by_num = []
        for key, value in rel_meta_by_name['fields'].items():
            if value['pkey']:
                pkey_by_num.append(value['fieldnum'])
        pkey = []
        for num in pkey_by_num:
            pkey.append(rel_meta_by_id[tableid]['fields'][num])
        return pkey
