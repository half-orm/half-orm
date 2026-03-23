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
import psycopg
from psycopg.rows import dict_row

from half_orm import relation_errors
from half_orm.transaction import Transaction
from half_orm.field import Field
from half_orm import utils
from half_orm.sql_ast import (
    Select as ASTSelect, Insert as ASTInsert, Update as ASTUpdate,
    Delete as ASTDelete, Join as ASTJoin, Raw as ASTRaw,
    Returning as ASTReturning,
    And as ASTAnd, Not as ASTNot, Group as ASTGroup, SetOp as ASTSetOp,
)

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
    def ho_select(self, *args: List[str],
        distinct:bool=False, order_by:str=None, limit:int=None, offset: int=None) -> [Dict]:
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

    def ho_assert_is_singleton(self):
        """
        A singleton is defined when all fields of a unique identifier are set
        with the '=' comparator. A unique identifier is either the primary key
        or any unique NOT NULL constraint. No database query is performed: the
        check is purely on the intention (the constraints set on the relation
        object).

        Returns:
            self
        Raises:
            NotASingletonError if self is not a singleton
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
        self._ho_fields_by_fieldnum = {}
        self._ho_pkey = {}
        self._ho_ukeys = []
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
        self._ho_ast_joins = []
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
    _HO_WRITABLE_KINDS = {'Table', 'Partioned table'}

    def _ho_check_writable(self):
        """Raise ReadOnlyRelationError if the relation does not support writes."""
        if self._ho_kind not in self._HO_WRITABLE_KINDS:
            from half_orm.relation_errors import ReadOnlyRelationError
            raise ReadOnlyRelationError(self)

    def _ho_prep_insert(self, *args):
        """Prepare an INSERT query. Returns (query, vals)."""
        self._ho_check_writable()
        _ = args and args != ('*',) and self._ho_check_colums(*args)
        self._ho_query_type = 'insert'
        fields_names, values, fk_fields, fk_query, fk_values = self.__what()
        placeholders = ["%s" for _ in range(len(values))]
        if fk_fields:
            fields_names += fk_fields
            placeholders += fk_query
            values += fk_values
        returning = args or ['*']
        stmt = ASTInsert(
            table=self._qrn,
            columns=fields_names,
            placeholders=placeholders,
            values=values,
            returning=ASTReturning(list(returning)),
        )
        query, vals = stmt.to_sql()
        return query, tuple(vals)

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
        query, vals = self._ho_prep_insert(*args)
        with self.__execute(query, vals) as cursor:
            res = [dict(elt) for elt in cursor.fetchall()] or [{}]
            return res[0]

    def _ho_result_is_relation(self, *args) -> bool:
        """Returns True if ho_select(*args) produces a proper relation in the
        relational-theory sense: the relation has a primary key (views without
        a PK return False) and all PK fields are present in the result,
        guaranteeing that each tuple is uniquely identifiable.

        Used to decide whether automatic deduplication applies when JOINs are present.
        """
        if not self._ho_pkey:
            return False  # views or relations without a PK are not proper relations
        if not args:
            return True  # all fields selected — PK is necessarily included
        return all(pk in args for pk in self._ho_pkey)

    #@utils.trace
    def _ho_prep_select_query(self, *args,
        distinct=False, order_by=None, limit=None, offset=None):
        """Validate select parameters and return (query, values, can_dedup, pk_names)."""
        self._ho_check_colums(*args)
        if limit is not None and not isinstance(limit, int):
            raise ValueError(f"limit must be an integer, got {type(limit).__name__!r}")
        if offset is not None and not isinstance(offset, int):
            raise ValueError(f"offset must be an integer, got {type(offset).__name__!r}")
        # TODO(1.0): remove fallback to _ho_select_params once deprecated methods are removed
        order_by = order_by or self._ho_select_params.get('order_by')
        limit = limit or self._ho_select_params.get('limit')
        offset = offset or self._ho_select_params.get('offset')
        distinct = 'distinct' if distinct or self._ho_select_params.get('distinct') else ''
        can_dedup = bool(self._ho_join_to) and self._ho_result_is_relation(*args)
        pk_names = list(self._ho_pkey.keys())
        query, values = self._ho_prep_select(
            *args, distinct=distinct, order_by=order_by, limit=limit, offset=offset)
        return query, values, can_dedup, pk_names

    def ho_select(self, *args,
        distinct:bool=False, order_by:str=None, limit:int=None, offset: int=None):
        """Gets the set of values correponding to the constraint attached to the object.
        This method is a generator.

        Arguments:
            *args: the fields names of the returned attributes. If omitted,
                all the fields are returned.
            distinct (bool): if True, adds DISTINCT to the SQL SELECT. Default: False.
            order_by (str): SQL ORDER BY clause (e.g. 'last_name, first_name'). Default: None.
            limit (int): maximum number of rows to return. Default: None (no limit).
            offset (int): number of rows to skip before returning results. Default: None.

        Yields:
            the result of the query as a dictionary.

        Example:
            >>> for person in Person(last_name=('like', 'La%')).ho_select('id', order_by='id', limit=10):
            >>>     print(person)
            {'id': 1772}
        """
        query, values, can_dedup, pk_names = self._ho_prep_select_query(
            *args, distinct=distinct, order_by=order_by, limit=limit, offset=offset)
        seen = set()
        dup_count = 0
        try:
            with self.__execute(query, values) as cursor:
                for elt in cursor:
                    row = dict(elt)
                    if can_dedup:
                        pk_key = tuple(row[pk] for pk in pk_names)
                        if pk_key in seen:
                            dup_count += 1
                            continue
                        seen.add(pk_key)
                    yield row
        finally:
            if dup_count:
                utils.warning(
                    f"{dup_count} duplicate(s) removed in"
                    f" ho_select on {self.__class__.__name__}."
                    f" Consider using distinct=True for better performance.\n"
                )

    def ho_assert_is_singleton(self):
        """
        A singleton is defined when all fields of a unique identifier are set
        with the '=' comparator. A unique identifier is either the primary key
        or any unique NOT NULL constraint. No database query is performed: the
        check is purely on the intention (the constraints set on the relation
        object).

        Returns:
            self
        Raises:
            NotASingletonError if self is not a singleton
        """
        def _fully_set(fields):
            return all(f.is_set() and f._comp() == '=' for f in fields.values())

        if self._ho_pkey and _fully_set(self._ho_pkey):
            return self
        for ukey in self._ho_ukeys:
            if _fully_set(ukey):
                return self
        if not self._ho_pkey and not self._ho_ukeys:
            raise relation_errors.NotASingletonError(
                f"{self.__class__.__name__} has no primary key or unique NOT NULL constraint.")
        raise relation_errors.NotASingletonError(
            f"No unique identifier fully set with '=' on {self.__class__.__name__}.")

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
                where = f"{where} and {fk_where}" if where else fk_where
            values += fk_values
        return where, values

    #@utils.trace
    def _ho_prep_update(self, *args, update_all=False, **kwargs):
        """Prepare an UPDATE query. Returns (query, vals, update_args) or None if nothing to update."""
        self._ho_check_writable()
        if not (self.ho_is_set() or update_all):
            raise RuntimeError(
                f'Attempt to update all rows of {self.__class__.__name__}'
                ' without update_all being set to True!')
        _ = args and args != ('*',) and self._ho_check_colums(*args)
        self._ho_check_colums(*(kwargs.keys()))
        update_args = {key: value for key, value in kwargs.items() if value is not None}
        if not update_args:
            return None
        self._ho_query_type = 'update'
        _, where_expr = self.__where_args()
        set_clause = []
        for field_name, new_value in update_args.items():
            col_name = self._ho_fields[field_name].name
            set_clause.append((f'"{col_name}" = %s', new_value))
        fk_where_str, fk_values = self.__fkey_where('', [])
        stmt = ASTUpdate(
            table=self._qrn,
            set_clause=set_clause,
            where=where_expr,
            fk_where=fk_where_str or None,
            fk_values=fk_values,
            returning=ASTReturning(list(args)) if args else None,
        )
        query, vals = stmt.to_sql()
        return query, tuple(vals), update_args

    def ho_update(self, *args, update_all=False, **kwargs):
        """
        kwargs represents the values to be updated {[field name:value]}
        The object self must be set unless update_all is True.
        The constraints of self are updated with kwargs.
        """
        prep = self._ho_prep_update(*args, update_all=update_all, **kwargs)
        if prep is None:
            return None
        query, vals, update_args = prep
        with self.__execute(query, vals) as cursor:
            for field_name, value in update_args.items():
                self._ho_fields[field_name].set(value)
            if args:
                return [dict(elt) for elt in cursor.fetchall()]
        return None

    def _ho_prep_delete(self, *args, delete_all=False):
        """Prepare a DELETE query. Returns (query, vals)."""
        self._ho_check_writable()
        _ = args and args != ('*',) and self._ho_check_colums(*args)
        if not (self.ho_is_set() or delete_all):
            raise RuntimeError(
                f'Attempt to delete all rows from {self.__class__.__name__}'
                ' without delete_all being set to True!')
        self._ho_query_type = 'delete'
        _, where_expr = self.__where_args()
        fk_where_str, fk_values = self.__fkey_where('', [])
        stmt = ASTDelete(
            table=self._qrn,
            where=where_expr,
            fk_where=fk_where_str or None,
            fk_values=fk_values,
            returning=ASTReturning(list(args)) if args else None,
        )
        query, vals = stmt.to_sql()
        return query, tuple(vals)

    #@utils.trace
    def ho_delete(self, *args, delete_all=False):
        """Removes a set of tuples from the relation.
        To empty the relation, delete_all must be set to True.
        """
        query, vals = self._ho_prep_delete(*args, delete_all=delete_all)
        with self.__execute(query, vals) as cursor:
            if args:
                return [dict(elt) for elt in cursor.fetchall()]
        return None

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

    async def __aexecute(self, query, values):
        return await self._ho_model.aexecute_query(query, values)

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

        ukeys = set()
        for field_name, f_metadata in _fields_metadata.items():
            field = Field(field_name, self, f_metadata)
            field_name = self.__py_field_name(field_name, f_metadata['fieldnum'])
            self._ho_fields[field_name] = field
            setattr(self, field_name, field)
            fieldnum = field._fieldnum()
            self._ho_fields_by_fieldnum[fieldnum] = field
            if field._is_part_of_pk():
                self._ho_pkey[field_name] = field
            if field._is_unique():
                pkeynum = tuple(field._pkeynum())
                if field.is_not_null():
                    ukeys.add(pkeynum)
                elif pkeynum in ukeys:
                    ukeys.remove(pkeynum)
        self._ho_ukeys = []
        for ukey in ukeys:
            ho_ukey = {}
            for fieldnum in ukey:
                field = self._ho_fields_by_fieldnum[fieldnum]
                ho_ukey[field.name] = field
            self._ho_ukeys.append(ho_ukey)

    def _ho_set_fkeys(self):
        """Initialisation of the foreign keys of the relation"""
        #pylint: disable=import-outside-toplevel
        from half_orm.fkey import FKey

        _fkeys_metadata = self._ho_model._fkeys_metadata(self._t_fqrn)
        for fkeyname, f_metadata in _fkeys_metadata.items():
            self._ho_fkeys[fkeyname] = FKey(fkeyname, self, *f_metadata)
        if not self._ho_fkeys_properties:
            aliased_fkeys = set()
            if hasattr(self.__class__, 'Fkeys'):
                for key, value in self.Fkeys.items():
                    try:
                        if key != '': # we skip empty keys
                            setattr(self, key, self._ho_fkeys[value])
                            self._ho_fkeys_attr.add(key)
                            aliased_fkeys.add(value)
                    except KeyError as exp:
                        raise relation_errors.WrongFkeyError(self, value) from exp
            # Auto-expose non-aliased FK with fk_/rfk_ prefix
            for fkeyname, fkey in self._ho_fkeys.items():
                if fkeyname in aliased_fkeys:
                    continue
                if fkeyname.startswith('_reverse_fkey_'):
                    attr_name = 'rfk_' + fkeyname[len('_reverse_fkey_'):]
                else:
                    attr_name = 'fk_' + fkeyname
                setattr(self, attr_name, fkey)
                self._ho_fkeys_attr.add(attr_name)
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

    def ho_where_display(self):
        """Returns the SQL JOIN and WHERE clauses as a dict, or None if no constraint.

        Returns:
            dict with keys:
                'joins'  : list of JOIN SQL strings (one per joined relation)
                'where'  : WHERE expression SQL string, or None
                'values' : list of string values (join values first, then where values)
            or None if the relation has no constraint set.
        """
        if not self.ho_is_set():
            return None
        saved_qtype = getattr(self, '_ho_query_type', None)
        self._ho_query_type = 'select'
        try:
            self.__get_from()
            expr = self.__walk_op(self.ho_id)
        finally:
            self._ho_query_type = saved_qtype
        joins = []
        all_values = []
        for join in self._ho_ast_joins:
            j_sql, j_vals = join.to_sql()
            joins.append(j_sql.strip())
            all_values.extend(j_vals)
        where = None
        if expr is not None:
            w_sql, w_vals = expr.to_sql()
            where = w_sql.replace(f'r{self.ho_id}.', '')
            all_values.extend(w_vals)
        if not joins and where is None:
            return None
        return {'joins': joins, 'where': where, 'values': [str(v) for v in all_values]}

    def __repr__(self):

        fkeys_usage = """\
Foreign keys are already accessible as fk_<name> (direct) or rfk_<name> (reverse) attributes.
To rename them, add a Fkeys class attribute: the aliased fk_/rfk_ attribute is then replaced
by the alias. Aliases must be unique and different from any column name. Empty string keys
are ignored.

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
    def __walk_op(self, rel_id_, _in_set_op_=False):
        """Walk the set operators tree and return an Expr node (or None).

        _in_set_op_: True when called as a child of a set operator. An
        unconstrained leaf must produce TRUE in that context so that it
        can be combined with AND / OR / NOT without generating invalid SQL.
        At the top level (False) an unconstrained leaf returns None so the
        WHERE clause is omitted entirely.
        """
        if self._ho_set_operators.operator:
            left = self._ho_set_operators.left
            left._ho_query_type = self._ho_query_type
            left_expr = left.__walk_op(rel_id_, True)

            if self._ho_set_operators.right is not None:
                right = self._ho_set_operators.right
                right._ho_query_type = self._ho_query_type
                right_expr = right.__walk_op(rel_id_, True)
                inner = ASTSetOp(
                    left=ASTGroup(left_expr),
                    operator=self._ho_set_operators.operator,
                    right=ASTGroup(right_expr),
                )
            else:
                inner = ASTGroup(left_expr)

            inner = ASTGroup(inner)
            if self._ho_neg:
                inner = ASTNot(inner)
            return inner
        else:
            expr = self.__where_expr(rel_id_)
            if expr is None:
                if _in_set_op_:
                    return ASTRaw("TRUE")
                return None
            return expr

    def _ho_sql_id(self):
        """Returns the FQRN as alias for the sql query."""
        return f"{self._qrn} as r{self.ho_id}"

    #@utils.trace
    def __get_from(self, orig_rel=None, deja_vu=None):
        """Constructs the AST join nodes for self."""
        if deja_vu is None:
            orig_rel = self
            self._ho_ast_joins = []
            deja_vu = {self.ho_id:[(self, None)]}
        for fkey, fk_rel in self._ho_join_to.items():
            fk_rel._ho_query_type = orig_rel._ho_query_type
            if fk_rel.ho_id not in deja_vu:
                deja_vu[fk_rel.ho_id] = []
            elif deja_vu[fk_rel.ho_id]:
                # fk_rel already joined (two fkeys pointing to the same relation)
                continue
            fk_rel.__get_from(orig_rel, deja_vu)
            deja_vu[fk_rel.ho_id].append((fk_rel, fkey))
            _, where_expr = fk_rel.__where_args()
            orig_rel._ho_ast_joins.insert(0, ASTJoin(
                table=fk_rel._ho_sql_id(),
                on=fkey._join_query(self),
                where=where_expr,
            ))

    #@utils.trace
    def __where_expr(self, rel_id_):
        """Returns an Expr node for this relation's field constraints, or None."""
        field_exprs = [
            field._where_expr(self._ho_query_type, rel_id_)
            for field in self.__get_set_fields()
        ]
        if not field_exprs:
            if self._ho_neg:
                return ASTRaw("FALSE")
            return None
        expr = ASTAnd(field_exprs) if len(field_exprs) > 1 else field_exprs[0]
        expr = ASTGroup(expr)
        if self._ho_neg:
            expr = ASTNot(expr)
        return expr

    #@utils.trace
    def __where_args(self, *args):
        """Returns the columns expression and WHERE Expr node.
        """
        rel_id_ = self.ho_id
        what = f'r{rel_id_}.*'
        if args:
            what = ', '.join([f'r{rel_id_}.{arg}' for arg in args])
        where_expr = self.__walk_op(rel_id_)
        return what, where_expr

    #@utils.trace
    def _ho_prep_select(self, *args,
        distinct:str='', order_by:str=None, limit:int=None, offset: int=None):
        from half_orm.fkey import FKey

        # Initialize state
        self._ho_ast_joins = []
        self._ho_query_type = 'select'

        # Get columns and WHERE expression
        what, where_expr = self.__where_args(*args)

        # Build joins (populates _ho_ast_joins)
        self.__get_from()

        # Validate FKeys
        for fkey_name in self._ho_fkeys_attr:
            fkey_cls = self.__dict__[fkey_name].__class__
            if fkey_cls != FKey:
                raise RuntimeError(
                    f'self.{fkey_name} is not a FKey (got a {fkey_cls.__name__} object instead).\n'
                    f'- use: self.{fkey_name}.set({fkey_cls.__name__}(...))\n'
                    f'- not: self.{fkey_name} = {fkey_cls.__name__}(...)'
                )

        # Deduplicate joins by table alias
        seen_tables = set()
        unique_joins = []
        for j in self._ho_ast_joins:
            if j.table not in seen_tables:
                seen_tables.add(j.table)
                unique_joins.append(j)

        # Build AST and render SQL
        stmt = ASTSelect(
            columns=[what],
            from_table=self._ho_sql_id(),
            only=bool(self._ho_only),
            joins=unique_joins,
            where=where_expr,
            distinct=bool(distinct),
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return stmt.to_sql()

    @utils._ho_deprecated(replacement="use ho_select(distinct=...)")
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

    @utils._ho_deprecated(replacement="use ho_select(order_by=...)")
    def ho_order_by(self, _order_):
        """Set SQL order by according to the "order" string passed

        @order string example :
        "field1, field2 desc, field3, field4 desc"
        """
        self._ho_select_params['order_by'] = _order_
        return self

    @utils._ho_deprecated(replacement="use ho_select(limit=...)")
    def ho_limit(self, _limit_):
        """Set limit for the next SQL select request."""
        if _limit_ is not None:
            self._ho_select_params['limit'] = int(_limit_)
        elif 'limit' in self._ho_select_params:
            self._ho_select_params.pop('limit')
        return self

    @utils._ho_deprecated(replacement="use ho_select(offset=...)")
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

    def _ho_prep_count(self, *args, distinct=False):
        """Prepare a COUNT query. Returns (query, values)."""
        self._ho_query = "select"
        distinct = 'distinct' if distinct or self._ho_select_params.get('distinct') else ''
        query, values = self._ho_prep_select(*args, distinct=distinct)
        query = f'select\n  count(*) from ({query}) as ho_count'
        return query, values

    # @utils.trace
    def ho_count(self, *args, distinct:bool=False):
        """Returns the number of tuples matching the intention in the relation.

        Arguments:
            *args: field names to count on (useful with distinct).
            distinct (bool): if True, adds DISTINCT to the inner SELECT. Default: False.
        """
        query, values = self._ho_prep_count(*args, distinct=distinct)
        return self.__execute(query, values).fetchone()['count']

    def ho_is_empty(self):
        """Returns True if the relation is empty, False otherwise.
        """
        return self.ho_count() == 0

    # --- Async variants of executor methods ---

    async def ho_ainsert(self, *args) -> dict:
        """Async variant of ho_insert."""
        query, vals = self._ho_prep_insert(*args)
        cursor = await self.__aexecute(query, vals)
        res = [dict(elt) for elt in await cursor.fetchall()] or [{}]
        return res[0]

    async def ho_aselect(self, *args,
        distinct: bool=False, order_by: str=None, limit: int=None, offset: int=None):
        """Async variant of ho_select. Returns a list of dicts (not a generator)."""
        query, values, can_dedup, pk_names = self._ho_prep_select_query(
            *args, distinct=distinct, order_by=order_by, limit=limit, offset=offset)
        cursor = await self.__aexecute(query, values)
        rows = []
        seen = set()
        for elt in await cursor.fetchall():
            row = dict(elt)
            if can_dedup:
                pk_key = tuple(row[pk] for pk in pk_names)
                if pk_key in seen:
                    continue
                seen.add(pk_key)
            rows.append(row)
        return rows

    async def ho_aupdate(self, *args, update_all=False, **kwargs):
        """Async variant of ho_update."""
        prep = self._ho_prep_update(*args, update_all=update_all, **kwargs)
        if prep is None:
            return None
        query, vals, update_args = prep
        cursor = await self.__aexecute(query, vals)
        for field_name, value in update_args.items():
            self._ho_fields[field_name].set(value)
        if args:
            return [dict(elt) for elt in await cursor.fetchall()]
        return None

    async def ho_adelete(self, *args, delete_all=False):
        """Async variant of ho_delete."""
        query, vals = self._ho_prep_delete(*args, delete_all=delete_all)
        cursor = await self.__aexecute(query, vals)
        if args:
            return [dict(elt) for elt in await cursor.fetchall()]
        return None

    async def ho_acount(self, *args, distinct: bool=False) -> int:
        """Async variant of ho_count."""
        query, values = self._ho_prep_count(*args, distinct=distinct)
        cursor = await self.__aexecute(query, values)
        row = await cursor.fetchone()
        return row['count']

    async def ho_ais_empty(self) -> bool:
        """Async variant of ho_is_empty."""
        return (await self.ho_acount()) == 0

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
        dct_join = dict(self._ho_join_to)
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

    # Relation objects are not hashable: __eq__ executes SQL queries.
    # Using a Relation as a dict key or in a set would be meaningless.
    __hash__ = None

    def __eq__(self, right):
        if id(self) == id(right):
            return True
        return ((self - right) | (right - self)).ho_is_empty()

    def __iter__(self):
        # TODO(1.0): remove _ho_select_params reads once deprecated methods are removed
        # (ho_distinct, ho_order_by, ho_limit, ho_offset)
        order_by = self._ho_select_params.get('order_by')
        limit = self._ho_select_params.get('limit')
        offset = self._ho_select_params.get('offset')
        distinct = 'distinct' if self._ho_select_params.get('distinct') else ''
        query, values = self._ho_prep_select(distinct=distinct, order_by=order_by, limit=limit, offset=offset)
        for elt in self.__execute(query, values):
            yield dict(elt)

    def __next__(self):
        return next(self.ho_select())

    # deprecated. To remove with release 1.0.0

    @utils._ho_deprecated(replacement='@singleton decorator or _ho_get')
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
    """Decorator. Enforces the intention to define a singleton.
    """
    @wraps(fct)
    def wrapper(self, *args, **kwargs):
        if self._ho_is_singleton:
            return fct(self, *args, **kwargs)
        self.ho_assert_is_singleton()
        return fct(self, *args, **kwargs)
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
