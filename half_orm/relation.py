#-*- coding: utf-8 -*-
# pylint: disable=protected-access, too-few-public-methods, no-member

"""This module is used by the `model <#module-half_orm.model>`_ module
to generate the classes that manipulate the data in your database
with the `Model.get_relation_class <#half_orm.model.Model.get_relation_class>`_
method.


Example:
    >>> from half_orm.model import Model
    >>> model = Model('halftest')
    >>> class Person(model.get_relation_class('actor.person')):
    >>>     # your code goes here

Main methods provided by the class Relation:
- ho_insert: inserts a tuple into the pg table.
- ho_select: returns a generator of the elements of the set defined by
  the constraint on the Relation object. The elements are dictionaries with the
  keys corresponding to the selected columns names in the relation.
  The result is affected by the methods: ho_distinct, ho_order_by, ho_limit and ho_offset
  (see below).
- ho_update: updates the set defined by the constraint on the Relation object
  with the values passed as arguments.
- ho_delete: deletes from the relation the set of elements defined by the constraint
  on the Relation object.
- ho_get: returns the unique element defined by the constraint on the Relation object.
  the element returned if of the type of the Relation object.

The following methods can be chained on the object before a select.

- ho_distinct: ensures that there are no duplicates on the select result.
- ho_order_by: sets the order of the select result.
- ho_limit: limits the number of elements returned by the select method.
- ho_offset: sets the offset for the select method.

"""

import inspect
from dataclasses import dataclass
from functools import wraps
from collections import OrderedDict
from typing import List, Generic, TypeVar, Dict, Optional
from keyword import iskeyword
import psycopg2
from psycopg2.extras import RealDictCursor

from half_orm import relation_errors
from half_orm.transaction import Transaction
from half_orm.field import Field
from half_orm import utils

class _SetOperators:
    """_SetOperators class stores the set operations made on the Relation class objects

    - __operator is one of {'or', 'and', 'sub', 'neg'}
    - __right is a Relation object. It can be None if the operator is 'neg'.
    """
    def __init__(self, left, operator=None, right=None):
        self.__left = left
        self.__operator = operator
        self.__right = right

    @property
    def operator(self):
        """Property returning the __operator value."""
        return self.__operator
    @operator.setter
    def operator(self, operator):
        """Set operator setter."""
        self.__operator = operator

    @property
    def left(self):
        """Returns the left object of the set operation."""
        return self.__left
    @left.setter
    def left(self, left):
        """left operand (relation) setter."""
        self.__left = left

    @property
    def right(self):
        """Property returning the right operand (relation)."""
        return self.__right
    @right.setter
    def right(self, right):
        """right operand setter."""
        self.__right = right

@dataclass
class DC_Relation: # pragma: no cover
    def __init__(self, **kwargs): ...

    def ho_insert(self, *args: List[str]) -> Dict:
        """Insert a new tuple into the Relation.

        Returns:
            Dict: A dictionary containing the data inserted.

        Example:
            >>> gaston = Person(last_name='La', first_name='Ga', birth_date='1970-01-01').ho_insert()
            >>> print(gaston)
            {'id': 1772, 'first_name': 'Ga', 'last_name': 'La', 'birth_date': datetime.date(1970, 1, 1)}

        Note:
            It is not possible to insert more than one row with the ho_insert method
        """
        ...
    def ho_select(self, *args: List[str]) -> [Dict]:
        """Gets the set of values correponding to the constraint attached to self.
        This method is a generator.

        Arguments:
            *args: the fields names of the returned attributes. If omitted,
                all the fields are returned.

        Yields:
            the result of the query as a list of dictionaries.

        Example:
            >>> for person in Person(last_name=('like', 'La%')).ho_select('id'):
            >>>     print(person)
            {'id': 1772}
        """
        ...

    def ho_update(self, *args, update_all=False, **kwargs) -> Optional[Dict]:
        """Updates the elements defined by self.

        Arguments:
            *args [Optional]: the list of columns names to return in the dictionary list for the updated elements.
                If args is ('*', ), returns all the columns values otherwise None.
            **kwargs: the values to be updated {[field name:value]}
            update_all: a boolean that must be set to True if there is no constraint on
                self. Defaults to False.
        """
        ...

    def ho_delete(self, *args, delete_all=False) -> [Dict]:
        """removes all elements from the set that correspond to the constraint.

        Arguments:
            *args [Optional]:
        """
        ...

    def _ho_get(self, *args: List[str]) -> 'Relation':
        """The get method allows you to fetch a singleton from the database.
        It garantees that the constraint references one and only one tuple.

        Arguments:
            args (List[str]): list of fields names.\
            If ommitted, all the values of the row retreived from the database\
            are set for the self object.\
            Otherwise, only the values listed in the `args` parameter are set.

        Returns:
            Relation: the object retreived from the database.

        Raises:
            ExpectedOneError: an exception is raised if no or more than one element is found.

        Example:
            >>> gaston = Person(last_name='Lagaffe', first_name='Gaston').ho_get()
            >>> type(gaston) is Person
            True
            >>> gaston.id
            (int4) NOT NULL (id = 1772)
            >>> str(gaston.id)
            '1772'
            >>> gaston.id.value
            1772
        """
        ...

    def ho_is_set(self) -> bool:
        """Return True if one field at least is set or if self has been
        constrained by at least one of its foreign keys or self is the
        result of a combination of Relations (using set operators).
        """
        ...

    def ho_distinct(self) -> 'Relation':
        """Set distinct for the SQL request."""
        ...

    def ho_unaccent(self, *fields_names) -> 'Relation':
        "Sets unaccent for each field listed in fields_names"
        ...

    def ho_order_by(self, _order_) -> 'Relation':
        """Sets the SQL `order by` according to the "_order_" string passed

        Example :
            personnes.ho_order_by("field1, field2 desc, field3, field4 desc")
        """
        ...

    def ho_limit(self, _limit_) -> 'Relation':
        """Sets the limit for the next SQL select request."""
        ...

    def ho_offset(self, _offset_) -> 'Relation':
        """Set the offset for the next SQL select request."""
        ...

    def ho_count(self, limit=0) -> int:
        """Returns the number of tuples matching the intention in the relation.
        """
        ...

    def ho_is_empty(self) -> bool:
        """Returns True if the self is an empty set, False otherwise.
        """
        ...

class Relation:
    """Used as a base class for the classes generated by
    `Model.get_relation_class <#half_orm.model.Model.get_relation_class>`_.

    Args:
        **kwargs: the arguments names must correspond to the columns names of the relation.

    Raises:
        UnknownAttributeError: If the name of an argument doesn't match a column name in the
            relation considered.

    Examples:
        You can generate a class for any relation in your database:
            >>> from half_orm.model import Model
            >>> model = Model('halftest')
            >>> class Person(model.get_relation_class('actor.person')):
            >>>     # your code

        To define a set of data in your relation at instantiation:
            >>> gaston = Person(last_name='Lagaffe', first_name='Gaston')
            >>> all_names_starting_with_la = Person(last_name=('ilike', 'la%'))

        Or to constrain an instantiated object via its\
            `Fields <#half_orm.field.Field>`_:
            >>> person = Person()
            >>> person.birth_date = ('>', '1970-01-01')

        Raises an `UnknownAttributeError <#half_orm.relation_errors.UnknownAttributeError>`_:
            >>> Person(lost_name='Lagaffe')
            [...]UnknownAttributeError: ERROR! Unknown attribute: {'lost_name'}.
    """
    _ho_fields_aliases = {}
    _rels_ids = {}

    def __init__(self, **kwargs):
        _fqrn = ""
        """The names of the arguments must correspond to the names of the columns in the relation.
        """
        module = __import__(self.__module__, globals(), locals(), ['FKEYS_PROPERTIES', 'FKEYS'], 0)
        #TODO: remove in release 1.0.0
        if hasattr(module, 'FKEYS_PROPERTIES') or hasattr(module, 'FKEYS'):
            mod_fkeys = utils.Color.bold(module.__name__ + '.FKEYS')
            err = f'''{mod_fkeys} variable is no longer supported!\n'''
            err += f'''\tUse the "{utils.Color.bold(self.__class__.__name__ + '.Fkeys')}"''' + \
                ''' class attribute instead.\n'''
            raise DeprecationWarning(err)
        self._ho_fk_loop = set()
        self._ho_fields = {}
        self._ho_pkey = {}
        self._ho_ukeys = OrderedDict()
        self._ho_fkeys = OrderedDict()
        self._ho_fkeys_attr = set()
        self._ho_join_to = {}
        self._ho_is_singleton = False
        self._ho_only = False
        self._ho_neg = False
        self._ho_set_fields()
        self._ho_set_fkeys()
        self._ho_query = ""
        self._ho_query_type = None
        self._ho_sql_query = []
        self._ho_sql_values = []
        self._ho_set_operators = _SetOperators(self)
        self._ho_select_params = {}
        self._ho_id_cast = None
        self._ho_mogrify = False
        self._ho_check_colums(*kwargs.keys())
        _ = {self.__dict__[field_name].set(value)
            for field_name, value in kwargs.items() if value is not None}
        self._ho_isfrozen = True

    def __call__(self, **kwargs):
        return self.__class__(**kwargs)

    def _ho_check_colums(self, *args):
        "Check that the args are actual columns of the relation"
        columns = {elt.replace('"', '') for elt in args}
        if columns.intersection(self._ho_fields.keys()) != columns:
            diff = columns.difference(self._ho_fields.keys())
            raise relation_errors.UnknownAttributeError(', '.join([elt for elt in args if elt in diff]))

    #@utils.trace
    def ho_insert(self, *args) -> '[dict]':
        """Insert a new tuple into the Relation.

        Returns:
            [dict]: A singleton containing the data inserted.

        Example:
            >>> gaston = Person(last_name='La', first_name='Ga', birth_date='1970-01-01').ho_insert()
            >>> print(gaston)
            {'id': 1772, 'first_name': 'Ga', 'last_name': 'La', 'birth_date': datetime.date(1970, 1, 1)}

        Note:
            It is not possible to insert more than one row with the insert method
        """
        _ = args and args != ('*',) and self._ho_check_colums(*args)
        query_template = "insert into {} ({}) values ({})"
        self._ho_query_type = 'insert'
        fields_names, values, fk_fields, fk_query, fk_values = self.__what()
        what_to_insert = ["%s" for _ in range(len(values))]
        if fk_fields:
            fields_names += fk_fields
            what_to_insert += fk_query
            values += fk_values
        query = query_template.format(self._qrn, ", ".join(fields_names), ", ".join(what_to_insert))
        returning = args or ['*']
        if returning:
            query = self._ho_add_returning(query, *returning)
        with self.__execute(query, tuple(values)) as cursor:
            res = [dict(elt) for elt in cursor.fetchall()] or [{}]
            return res[0]

    #@utils.trace
    def ho_select(self, *args):
        """Gets the set of values correponding to the constraint attached to the object.
        This method is a generator.

        Arguments:
            *args: the fields names of the returned attributes. If omitted,
                all the fields are returned.

        Yields:
            the result of the query as a dictionary.

        Example:
            >>> for person in Person(last_name=('like', 'La%')).ho_select('id'):
            >>>     print(person)
            {'id': 1772}
        """
        self._ho_check_colums(*args)
        query, values = self._ho_prep_select(*args)
        with self.__execute(query, values) as cursor:
            for elt in cursor:
                yield dict(elt)

    #@utils.trace
    def _ho_get(self, *args: List[str]) -> 'Relation':
        """The get method allows you to fetch a singleton from the database.
        It garantees that the constraint references one and only one tuple.

        Args:
            args (List[str]): list of fields names.\
            If ommitted, all the values of the row retreived from the database\
            are set for the self object.\
            Otherwise, only the values listed in the `args` parameter are set.

        Returns:
            Relation: the object retreived from the database.

        Raises:
            ExpectedOneError: an exception is raised if no or more than one element is found.

        Example:
            >>> gaston = Person(last_name='Lagaffe', first_name='Gaston')._ho_get()
            >>> type(gaston) is Person
            True
            >>> gaston.id
            (int4) NOT NULL (id = 1772)
            >>> str(gaston.id)
            '1772'
            >>> gaston.id.value
            1772
        """
        self._ho_check_colums(*args)
        self.ho_limit(2)
        _count = self.ho_count()
        if _count != 1:
            raise relation_errors.ExpectedOneError(self, _count)
        self._ho_is_singleton = True
        ret = self(**(next(self.ho_select(*args))))
        ret._ho_is_singleton = True
        return ret

    #@utils.trace
    def __fkey_where(self, where, values):
        _, _, fk_fields, fk_query, fk_values = self.__what()
        if fk_fields:
            fk_where = " and ".join([f"({a}) in ({b})" for a, b in zip(fk_fields, fk_query)])
            if fk_where:
                where = f"{where} and {fk_where}"
            values += fk_values
        return where, values

    #@utils.trace
    def ho_update(self, *args, update_all=False, **kwargs):
        """
        kwargs represents the values to be updated {[field name:value]}
        The object self must be set unless update_all is True.
        The constraints of self are updated with kwargs.
        """
        if not (self.ho_is_set() or update_all):
            raise RuntimeError(
                f'Attempt to update all rows of {self.__class__.__name__}'
                ' without update_all being set to True!')

        _ = args and args != ('*',) and self._ho_check_colums(*args)
        self._ho_check_colums(*(kwargs.keys()))
        update_args = {key: value for key, value in kwargs.items() if value is not None}
        if not update_args:
            return None # no new value update. Should we raise an error here?

        query_template = "update {} set {} {}"
        what, where, values = self.__update_args(**update_args)
        where, values = self.__fkey_where(where, values)
        query = query_template.format(self._qrn, what, where)
        if args:
            query = self._ho_add_returning(query, *args)
        with self.__execute(query, tuple(values)) as cursor:
            for field_name, value in update_args.items():
                self._ho_fields[field_name].set(value)
            if args:
                return [dict(elt) for elt in cursor.fetchall()]
        return None

    #@utils.trace
    def ho_delete(self, *args, delete_all=False):
        """Removes a set of tuples from the relation.
        To empty the relation, delete_all must be set to True.
        """
        _ = args and args != ('*',) and self._ho_check_colums(*args)
        if not (self.ho_is_set() or delete_all):
            raise RuntimeError(
                f'Attempt to delete all rows from {self.__class__.__name__}'
                ' without delete_all being set to True!')
        query_template = "delete from {} {}"
        _, values = self.__prep_query(query_template)
        self._ho_query_type = 'delete'
        _, where, _ = self.__where_args()
        where, values = self.__fkey_where(where, values)
        if where:
            where = f" where {where}"
        query = f"delete from {self._qrn} {where}"
        if args:
            query = self._ho_add_returning(query, *args)
        with self.__execute(query, tuple(values)) as cursor:
            if args:
                return [dict(elt) for elt in cursor.fetchall()]
        return None

    def _ho_add_returning(self, query, *args) -> str:
        "Adds the SQL returning clause to the query"
        if args:
            returning = ', '.join(args)
            return f'{query} returning {returning}'
        return query

    def ho_unfreeze(self):
        "Allow to add attributs to a relation"
        self._ho_isfrozen = False

    def ho_freeze(self):
        "set _ho_isfrozen to True."
        self._ho_isfrozen = True

    def __setattr__(self, key, value):
        """Sets an attribute as long as _ho_isfrozen is False

        The foreign keys properties are not detected by hasattr
        hence the line `_ = self.__dict__[key]` to double check if
        the attribute is really present.
        """
        if not hasattr(self, '_ho_isfrozen'):
            object.__setattr__(self, '_ho_isfrozen', False)
        if self._ho_isfrozen and not hasattr(self, key):
            raise relation_errors.IsFrozenError(self.__class__, key)
        if self.__dict__.get(key) and isinstance(self.__dict__[key], Field):
            self.__dict__[key].set(value)
            return
        object.__setattr__(self, key, value)

    #@utils.trace
    def __execute(self, query, values):
        if self._ho_model.sql_trace:
            caller_info = utils.get_caller_info(skip_frames=2)
            if caller_info:
                print(f"\n{utils.Color.blue('SQL TRACE')}:")
                print(f"  File: {caller_info['filename']}:{caller_info['lineno']}")
                print(f"  Function: {caller_info['function']}")
                print(f"  Code: {caller_info['code_context']}")
        return self._ho_model.execute_query(query, values, self._ho_mogrify)

    @property
    def ho_id(self):
        """Return the _ho_id_cast or the id of the relation.
        """
        return self._ho_id_cast or id(self)

    @property
    def ho_only(self):
        "Returns the value of self._ho_only"
        return self._ho_only
    @ho_only.setter
    def ho_only(self, value):
        """Set the value of self._ho_only. Restrict the values of a query to
        the elements of the relation (no inherited values).
        """
        if value not in {True, False}:
            raise ValueError(f'{value} is not a bool!')
        self._ho_only = value

    def __py_field_name(self, name, field_num):
        py_name = self._ho_fields_aliases.get(name, name)
        error = utils.check_attribute_name(py_name)
        if error is not None:
            utils.warning(f"{error}\n", 'HALFORM')
            return f'column{field_num}'
        return py_name

    def _ho_set_fields(self):
        """Initialise the fields of the relation."""
        _fields_metadata = self._ho_model._fields_metadata(self._t_fqrn)

        for field_name, f_metadata in _fields_metadata.items():
            field = Field(field_name, self, f_metadata)
            field_name = self.__py_field_name(field_name, f_metadata['fieldnum'])
            self._ho_fields[field_name] = field
            setattr(self, field_name, field)
            if field._is_part_of_pk():
                self._ho_pkey[field_name] = field
            if field._is_unique():
                self._ho_ukeys[field_name] = field

    def _ho_set_fkeys(self):
        """Initialisation of the foreign keys of the relation"""
        #pylint: disable=import-outside-toplevel
        from half_orm.fkey import FKey

        _fkeys_metadata = self._ho_model._fkeys_metadata(self._t_fqrn)
        for fkeyname, f_metadata in _fkeys_metadata.items():
            self._ho_fkeys[fkeyname] = FKey(fkeyname, self, *f_metadata)
        if hasattr(self.__class__, 'Fkeys') and not self._ho_fkeys_properties:
            for key, value in self.Fkeys.items():
                try:
                    if key != '': # we skip empty keys
                        setattr(self, key, self._ho_fkeys[value])
                        self._ho_fkeys_attr.add(key)
                except KeyError as exp:
                    raise relation_errors.WrongFkeyError(self, value) from exp
        self._ho_fkeys_properties = True

    @classmethod
    def _ho_dataclass_name(cls):
        database, schema, relation = cls._t_fqrn
        schemaname = ''.join([elt.capitalize() for elt in schema.split('.')])
        relationname = ''.join([elt.capitalize() for elt in relation.split('_')])
        return f'DC_{schemaname}{relationname}'

    def ho_dict(self):
        """Returns a dictionary containing only the values of the fields
        that are set."""
        return {key:field.value for key, field in self._ho_fields.items() if field.is_set()}

    def keys(self):
        return self._ho_fields.keys()

    def items(self):
        for key, field in self._ho_fields.items():
            yield key, field.value

    def __getitem__(self, key):
        return self._ho_fields[key].value

    def __to_dict_val_comp(self):
        """Returns a dictionary containing the values and comparators of the fields
        that are set."""
        return {key:(field._comp(), field.value) for key, field in
                self._ho_fields.items() if field.is_set()}

    def __repr__(self):

        fkeys_usage = """\
To use the foreign keys as direct attributes of the class, copy/paste the Fkeys below into
your code as a class attribute and replace the empty string key(s) with the alias(es) you
want to use. The aliases must be unique and different from any of the column names. Empty
string keys are ignored.

Fkeys = {"""

        rel_kind = self._ho_kind
        ret = []
        database, schema, relation = self._t_fqrn
        ret.append(f"DATABASE: {database}")
        ret.append(f"SCHEMA: {schema}")
        ret.append(f"{rel_kind.upper()}: {relation}\n")
        if self._ho_metadata['description']:
            ret.append(f"DESCRIPTION:\n{self._ho_metadata['description']}")
        ret.append('FIELDS:')
        mx_fld_n_len = 0
        for field_name in self._ho_fields.keys():
            mx_fld_n_len = max(mx_fld_n_len, len(field_name))
        for field_name, field in self._ho_fields.items():
            field_desc = f"- {field_name}:{' ' * (mx_fld_n_len + 1 - len(field_name))}{repr(field)}"
            error = utils.check_attribute_name(field.name)
            if error and not field.name in self._ho_fields_aliases:
                field_desc = f'{field_desc} --- FIX ME! {error}'
            ret.append(field_desc)
        ret.append('')
        pkey = self._ho_model._pkey_constraint(self._t_fqrn)
        if pkey:
            ret.append(f"PRIMARY KEY ({', '.join(pkey)})")
        for uniq in self._ho_model._unique_constraints_list(self._t_fqrn):
            ret.append(f"UNIQUE CONSTRAINT ({', '.join(uniq)})")
        if self._ho_fkeys.keys():
            plur = 'S' if len(self._ho_fkeys) > 1 else ''
            ret.append(f'FOREIGN KEY{plur}:')
            for fkey in self._ho_fkeys.values():
                ret.append(repr(fkey))
            ret.append('')
            if not hasattr(self, 'Fkeys'):
                ret.append(fkeys_usage)
                for fkey in self._ho_fkeys:
                    ret.append(f"    '': '{fkey}',")
            else:
                ret.append("Fkeys = {")
                for key, value in self.Fkeys.items():
                    ret.append(f"    '{key}': '{value}',")
            ret.append('}')
        return '\n'.join(ret)

    def ho_is_set(self):
        """Return True if one field at least is set or if self has been
        constrained by at least one of its foreign keys or self is the
        result of a combination of Relations (using set operators).
        """
        joined_to = False
        for _, jt_ in self._ho_join_to.items():
            jt_id = id(jt_)
            if jt_id in self._ho_fk_loop:
                raise RuntimeError("Can't set Fkey on the same object")
            self._ho_fk_loop.add(jt_id)
            joined_to |= jt_.ho_is_set()
        self._ho_fk_loop = set()
        return (joined_to or bool(self._ho_set_operators.operator) or bool(self._ho_neg) or
                bool({field for field in self._ho_fields.values() if field.is_set()}))

    def __get_set_fields(self):
        """Returns a list containing only the fields that are set."""
        return [field for field in self._ho_fields.values() if field.is_set()]

    #@utils.trace
    def __walk_op(self, rel_id_, out=None, _fields_=None):
        """Walk the set operators tree and return a list of SQL where
        representation of the query with a list of the fields of the query.
        """
        if out is None:
            out = []
            _fields_ = []
        if self._ho_set_operators.operator:
            if self._ho_neg:
                out.append("not (")
            out.append("(")
            left = self._ho_set_operators.left
            left._ho_query_type = self._ho_query_type
            left.__walk_op(rel_id_, out, _fields_)
            if self._ho_set_operators.right is not None:
                out.append(f" {self._ho_set_operators.operator}\n    ")
                right = self._ho_set_operators.right
                right._ho_query_type = self._ho_query_type
                right.__walk_op(rel_id_, out, _fields_)
            out.append(")")
            if self._ho_neg:
                out.append(")")
        else:
            out.append(self.__where_repr(rel_id_))
            _fields_ += self.__get_set_fields()
        return out, _fields_

    def _ho_sql_id(self):
        """Returns the FQRN as alias for the sql query."""
        return f"{self._qrn} as r{self.ho_id}"

    #@utils.trace
    def __get_from(self, orig_rel=None, deja_vu=None):
        """Constructs the _ho_sql_query and gets the _ho_sql_values for self."""
        if deja_vu is None:
            orig_rel = self
            self._ho_sql_query = [self._ho_sql_id()]
            deja_vu = {self.ho_id:[(self, None)]}
        for fkey, fk_rel in self._ho_join_to.items():
            fk_rel._ho_query_type = orig_rel._ho_query_type
            if fk_rel.ho_id not in deja_vu:
                deja_vu[fk_rel.ho_id] = []
            # elif (fk_rel, fkey) in deja_vu[fk_rel.ho_id] or fk_rel is orig_rel:
            #     #sys.stderr.write(f"déjà vu in from! {fk_rel._fqrn}\n")
            #     continue
            fk_rel.__get_from(orig_rel, deja_vu)
            deja_vu[fk_rel.ho_id].append((fk_rel, fkey))
            _, where, values = fk_rel.__where_args()
            where = f" and\n {where}"
            orig_rel._ho_sql_query.insert(1, f'\n  join {fk_rel._ho_sql_id()} on\n   ')
            orig_rel._ho_sql_query.insert(2, fkey._join_query(self))
            orig_rel._ho_sql_query.append(where)
            orig_rel._ho_sql_values += values

    #@utils.trace
    def __where_repr(self, rel_id_):
        where_repr = []
        for field in self.__get_set_fields():
            where_repr.append(field._where_repr(self._ho_query_type, rel_id_))
        where_repr = ' and '.join(where_repr) or '1 = 1'
        ret = f"({where_repr})"
        if self._ho_neg:
            ret = f"not ({ret})"
        return ret

    #@utils.trace
    def __where_args(self, *args):
        """Returns the what, where and values needed to construct the queries.
        """
        rel_id_ = self.ho_id
        what = f'r{rel_id_}.*'
        if args:
            what = ', '.join([f'r{rel_id_}.{arg}' for arg in args])
        s_where, set_fields = self.__walk_op(rel_id_)
        s_where = ''.join(s_where)
        return what, s_where, set_fields

    #@utils.trace
    def __prep_query(self, query_template, *args):
        """Prepare the SQL query to be executed."""
        from half_orm.fkey import FKey
        self._ho_sql_values = []
        self._ho_query_type = 'select'
        what, where, values = self.__where_args(*args)
        where = f"\nwhere\n    {where}"
        self.__get_from()
        # remove duplicates
        for idx, elt in reversed(list(enumerate(self._ho_sql_query))):
            if elt.find('\n  join ') == 0 and self._ho_sql_query.count(elt) > 1:
                self._ho_sql_query[idx] = '  and\n'
        # check that fkeys are fkeys
        for fkey_name in self._ho_fkeys_attr:
            fkey_cls = self.__dict__[fkey_name].__class__
            if fkey_cls != FKey:
                raise RuntimeError(
                    f'self.{fkey_name} is not a FKey (got a {fkey_cls.__name__} object instead).\n'
                    f'- use: self.{fkey_name}.set({fkey_cls.__name__}(...))\n'
                    f'- not: self.{fkey_name} = {fkey_cls.__name__}(...)'
                    )
        return (
            query_template.format(
                what,
                self._ho_only and "only" or "",
                ' '.join(self._ho_sql_query), where),
            values)

    #@utils.trace
    def _ho_prep_select(self, *args):
        distinct = self._ho_select_params.get('distinct', '')
        query_template = f"select\n {distinct} {{}}\nfrom\n  {{}} {{}}\n  {{}}"
        query, values = self.__prep_query(query_template, *args)
        values = tuple(self._ho_sql_values + values)
        if 'order_by' in self._ho_select_params:
            query = f"{query} order by {self._ho_select_params['order_by']}"
        if 'limit' in self._ho_select_params:
            query = f"{query} limit {self._ho_select_params['limit']}"
        if 'offset' in self._ho_select_params:
            query = f"{query} offset {self._ho_select_params['offset']}"
        return query, values

    def ho_distinct(self, dist=True):
        """Set distinct in SQL select request."""
        distinct = 'distinct'
        if dist not in {True, False}:
            raise ValueError('ho_distinct argument must be either True or False!')
        if dist in {False, None}:
            distinct = ''
        self._ho_select_params['distinct'] = distinct
        return self

    def ho_unaccent(self, *fields_names):
        "Sets unaccent for each field listed in fields_names"
        for field_name in fields_names:
            if not isinstance(self.__dict__[field_name], Field):
                raise ValueError(f'{field_name} is not a Field!')
            self.__dict__[field_name].unaccent = True
        return self

    def ho_order_by(self, _order_):
        """Set SQL order by according to the "order" string passed

        @order string example :
        "field1, field2 desc, field3, field4 desc"
        """
        self._ho_select_params['order_by'] = _order_
        return self

    def ho_limit(self, _limit_):
        """Set limit for the next SQL select request."""
        if _limit_ is not None:
            self._ho_select_params['limit'] = int(_limit_)
        elif 'limit' in self._ho_select_params:
            self._ho_select_params.pop('limit')
        return self

    def ho_offset(self, _offset_):
        """Set the offset for the next SQL select request."""
        if _offset_ is not None:
            self._ho_select_params['offset'] = int(_offset_)
        elif 'offset' in self._ho_select_params:
            self._ho_select_params.pop('offset')
        return self

    def ho_mogrify(self):
        """Prints the select query."""
        self._ho_mogrify = True
        return self

    # @utils.trace
    def ho_count(self, *args):
        """Returns the number of tuples matching the intention in the relation.
        """
        self._ho_query = "select"
        query, values = self._ho_prep_select(*args)
        query = f'select\n  count(*) from ({query}) as ho_count'
        return self.__execute(query, values).fetchone()['count']

    def ho_is_empty(self):
        """Returns True if the relation is empty, False otherwise.
        """
        self.ho_limit(1)
        return self.ho_count() == 0

    #@utils.trace
    def __update_args(self, **kwargs):
        """Returns the what, where an values for the update query."""
        what_fields = []
        new_values = []
        self._ho_query_type = 'update'
        _, where, values = self.__where_args()
        where = f" where {where}"
        for field_name, new_value in kwargs.items():
            what_fields.append(self._ho_fields[field_name].name)
            new_values.append(new_value)
        what = ", ".join([f'"{elt}" = %s' for elt in what_fields])
        return what, where, new_values + values

    #@utils.trace
    def __what(self):
        """Returns the constrained fields and foreign keys.
        """
        set_fields = self.__get_set_fields()
        fields_names = [
            f'"{field.name}"' for field in self._ho_fields.values() if field.is_set()]
        fk_fields = []
        fk_queries = ''
        fk_values = []
        for fkey in self._ho_fkeys.values():
            fk_prep_select = fkey._fkey_prep_select()
            if fk_prep_select is not None and len(fkey.values()) and len(fk_prep_select):
                fk_values += list(fkey.values()[0])
                fk_fields += fk_prep_select[0]
                fk_queries = ["%s" for _ in range(len(fk_values))]

        return fields_names, set_fields, fk_fields, fk_queries, fk_values

    @classmethod
    def ho_description(cls):
        """Returns the description (comment) of the relation
        """
        description = cls._ho_metadata['description']
        if description:
            description = description.strip()
        return description or 'No description available'

    def ho_cast(self, qrn):
        """Cast a relation into another relation.

        TODO: check that qrn inherits self (or is inherited by self)?
        """
        new = self._ho_model._import_class(qrn)(**self.__to_dict_val_comp())
        new._ho_id_cast = id(self)
        new._ho_join_to = self._ho_join_to
        new._ho_set_operators = self._ho_set_operators
        return new

    def __set__op__(self, operator=None, right=None):
        """Si l'opérateur du self est déjà défini, il faut aller modifier
        l'opérateur du right ???
        On crée un nouvel objet sans contrainte et on a left et right et opérateur
        """
        def check_fk(new, jt_list):
            """Sets the _ho_join_to dictionary for the new relation.
            """
            for fkey, rel in jt_list.items():
                if rel is self:
                    rel = new
                new._ho_join_to[fkey] = rel
        new = self(**self.__to_dict_val_comp())
        new._ho_id_cast = self._ho_id_cast
        if operator:
            new._ho_set_operators.left = self
            new._ho_set_operators.operator = operator
        dct_join = self._ho_join_to
        if right is not None:
            new._ho_set_operators.right = right
            dct_join.update(right._ho_join_to)
        check_fk(new, dct_join)
        return new

    def __and__(self, right):
        return self.__set__op__("and", right)
    def __iand__(self, right):
        self = self & right
        return self

    def __or__(self, right):
        return self.__set__op__("or", right)
    def __ior__(self, right):
        self = self | right
        return self

    def __sub__(self, right):
        return self.__set__op__("and not", right)
    def __isub__(self, right):
        self = self - right
        return self

    def __neg__(self):
        new = self.__set__op__(self._ho_set_operators.operator, self._ho_set_operators.right)
        new._ho_neg = not self._ho_neg
        return new

    def __xor__(self, right):
        return (self | right) - (self & right)
    def __ixor__(self, right):
        self = self ^ right
        return self

    def __contains__(self, right):
        return (right - self).ho_count() == 0

    def __eq__(self, right):
        if id(self) == id(right):
            return True
        return ((self - right) | (right - self)).ho_is_empty()

    def __enter__(self):
        """Context management entry

        Returns self in a transaction context.

        Example usage:
        with relation as rel:
            rel.ho_update(col=new_val)

        Equivalent to (in a transaction context):
        rel = relation.ho_select()
        for elt in rel:
            new_elt = relation(**elt)
            new_elt.ho_update(col=new_val)
        """
        self.ho_transaction._enter(self._ho_model)
        return self

    def __exit__(self, *__):
        """Context management exit

        """
        self.ho_transaction._exit(self._ho_model)
        return False

    def __iter__(self):
        query, values = self._ho_prep_select()
        for elt in self.__execute(query, values):
            yield dict(elt)

    def __next__(self):
        return next(self.ho_select())

    # deprecated. To remove with release 1.0.0

    @utils._ho_deprecated
    def ho_get(self, *args, **kwargs):
        return self._ho_get(*args, **kwargs)

    @utils._ho_deprecated
    def select(self, *args): # pragma: no cover
        return self.ho_select(*args)

    @utils._ho_deprecated
    def insert(self, *args): # pragma: no cover
        return self.ho_insert(*args)

    @utils._ho_deprecated
    def update(self, *args, update_all=False, **kwargs): # pragma: no cover
        return self.ho_update(*args, update_all, **kwargs)

    @utils._ho_deprecated
    def delete(self, *args, delete_all=False): # pragma: no cover
        return self.ho_delete(*args, delete_all)

    @utils._ho_deprecated
    def get(self, *args): # pragma: no cover
        return self.ho_get(*args)

    @utils._ho_deprecated
    def unaccent(self, *fields_names): # pragma: no cover
        return self.ho_unaccent(*fields_names)

    @utils._ho_deprecated
    def order_by(self, _order_): # pragma: no cover
        return self.ho_order_by(_order_)

    @utils._ho_deprecated
    def limit(self, _limit_): # pragma: no cover
        return self.ho_limit(_limit_)

    @utils._ho_deprecated
    def offset(self, _offset_): # pragma: no cover
        return self.ho_offset(_offset_)

    @utils._ho_deprecated
    def _mogrify(self): # pragma: no cover
        return self.ho_mogrify()

    @utils._ho_deprecated
    def count(self, *args): # pragma: no cover
        return self.ho_count(*args)

    @utils._ho_deprecated
    def is_empty(self): # pragma: no cover
        return self.ho_is_empty()

def singleton(fct):
    """Decorator. Enforces the relation to define a singleton.

    _ho_is_singleton is set by Relation.get.
    _ho_is_singleton is unset as soon as a Field is set.
    """
    @wraps(fct)
    def wrapper(self, *args, **kwargs):
        if self._ho_is_singleton:
            return fct(self, *args, **kwargs)
        try:
            self = self.ho_get()
            return fct(self, *args, **kwargs)
        except relation_errors.ExpectedOneError as err:
            raise relation_errors.NotASingletonError(err)
    wrapper.__is_singleton = True
    wrapper.__orig_args = inspect.getfullargspec(fct)
    return wrapper

def transaction(fct):
    """Decorator. Enforces every SQL insert, update or delete operation called within a
    Relation method to be executed in a transaction.
    
    Usage:
        from relation import transaction
        class Person(model.get_relation_class(actor.person)):
            [...]
            @transaction
            def insert_many(self, **data):
                for d_pers in **data:
                    self(**d_pers).ho_insert()
            [...]
        
        Pers().insert_many([{...}, {...}])

    """
    @wraps(fct)
    def wrapper(self, *args, **kwargs):
        with Transaction(self._ho_model):
            return fct(self, *args, **kwargs)
    return wrapper
