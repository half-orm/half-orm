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

def normalize_fqrn(t_fqrn: tuple) -> str:
    """
    Transform the tuple (<db name>, <schema name>, <table name>) in
    "<db name>":"<schema name>"."<table name>".
    Dots are allowed only in the schema name.
    """
    dbname, schemaname, tablename = t_fqrn
    return f'"{dbname}":"{schemaname}"."{tablename}"'

def normalize_qrn(t_qrn):
    """
    qrn is a tuple for the qualified relation name (<schema name>, <talbe name>)
    A schema name can have any number of dots in it.
    A table name can't have a dot in it.
    returns "<schema name>"."<relation name>"
    """
    return '.'.join([f'"{elt}"' for elt in __get_qrn(t_qrn)])

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
    cn_fk.confdeltype as fkey_confdeltype
FROM
    pg_class c -- table
    LEFT JOIN pg_description tdesc ON
    tdesc.objoid = c.oid AND
    tdesc.objsubid = 0
    LEFT JOIN pg_namespace n ON
    n.oid = c.relnamespace
    LEFT JOIN pg_inherits i ON
    i.inhrelid = c.oid
    LEFT JOIN pg_attribute a ON
    a.attrelid = c.oid
    LEFT JOIN pg_description adesc ON
    adesc.objoid = c.oid AND
    adesc.objsubid = a.attnum
    JOIN pg_type pt ON
    a.atttypid = pt.oid
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
    cn_fk.confdeltype
ORDER BY
    n.nspname, c.relname, a.attnum
"""

class _Meta(dict):
    __d_meta = {}

    @classmethod
    def deja_vu(cls, dbname):
        return dbname in cls.__d_meta

    @classmethod
    def register(cls, dbname, meta):
        cls.__d_meta[dbname] = meta

    def __getitem__(self, key):
        return _Meta.__d_meta.__getitem__(key)

class PgMeta:
    """A utility class for loading and storing metadata of a PostgreSQL database.

    Attributes:
        meta (_Meta): A singleton instance of the `_Meta` class.
    """
    meta = _Meta()
    def __init__(self, connection, reload=False):
        """Initializes a new instance of the `PgMeta` class.

        Args:
            connection (psycopg.extensions.connection): A connection object to a PostgreSQL database.
            reload (bool, optional): A flag indicating whether to reload the metadata from the database. \
            Defaults to False.
        """
        self.__dbname = connection.info.get_parameters()['dbname']
        if not PgMeta.meta.deja_vu(self.__dbname) or reload:
            self.__load_metadata(connection)

    def metadata(self, dbname):
        """Retrieves the metadata for the specified database name.

        Args:
            dbname (str): The name of the PostgreSQL database.

        Returns:
            dict: The metadata of the specified database.
        """
        return self.meta[dbname]

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
        """
        metadata = {'relations_list': []}
        byname = metadata['byname'] = OrderedDict()
        byid = metadata['byid'] = {}
        with connection.cursor(row_factory=dict_row) as cur:
            cur.execute(_REQUEST)
            all_ = [elt for elt in cur.fetchall()]
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
                fieldname = dct.pop('fieldname')
                fieldnum = dct['fieldnum']
                tablekind = dct.pop('tablekind')
                inherits = [byid[int(elt.split(':')[1])]['sfqrn']
                            for elt in dct.pop('inherits') if elt is not None]
                byname[table_key]['tableid'] = tableid
                byname[table_key]['tablekind'] = tablekind
                byname[table_key]['inherits'] = inherits
                byname[table_key]['fields'][fieldname] = dct
                byname[table_key]['fields_by_num'][fieldnum] = dct
                byid[tableid]['fields'][fieldnum] = fieldname
                if (tablekind, table_key) not in metadata['relations_list']:
                    metadata['relations_list'].append((tablekind, table_key))
            for dct in all_:
                tableid = dct['tableid']
                table_key = byid[tableid]['sfqrn']
                fkeyname = dct['fkeyname']
                if fkeyname and fkeyname not in byname[table_key]['fkeys']:
                    fkeytableid = dct['fkeytableid']
                    ftable_key = byid[fkeytableid]['sfqrn']
                    fields = [byid[tableid]['fields'][num] for num in dct['lfkeynum']]
                    confupdtype = dct['fkey_confupdtype']
                    confdeltype = dct['fkey_confdeltype']
                    ffields = [byid[fkeytableid]['fields'][num] for num in dct['fkeynum']]
                    rev_fkey_name = f'_reverse_fkey_{"_".join(table_key)}.{".".join(fields)}'
                    rev_fkey_name = strip_quotes(rev_fkey_name.replace(".", "_").replace(":", "_"))
                    byname[table_key]['fkeys'][fkeyname] = (
                        ftable_key, ffields, fields, confupdtype, confdeltype)
                    byname[ftable_key]['fkeys'][rev_fkey_name] = (table_key, fields, ffields, confupdtype, confdeltype)

        metadata['relations_list'].sort()
        PgMeta.meta.register(self.__dbname, metadata)

    def has_relation(self, dbname, schema, relation):
        """Checks whether the specified relation exists in the specified database.

        Args:
            dbname (str): The name of the PostgreSQL database.
            schema (str): The name of the schema containing the relation.
            relation (str): The name of the relation.

        Returns:
            bool: True if the relation exists, False otherwise.
        """
        return (dbname, schema, relation) in self.meta[dbname]['byname']


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
            if key[1].find('half_orm_meta') == 0: continue
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
