#-*- coding: utf-8 -*-
# pylint: disable=protected-access

"""This module provides the Field class. It is used by the `relation <#module-half_orm.relation>`_ module."""

import sys
import typing
from collections.abc import Iterable
from half_orm.null import NULL
from half_orm.sql_adapter import SQL_ADAPTER
from half_orm.sql_ast import FieldExpr

class Field():
    """The class Field is for Relation internal usage. It is called by
    the RelationFactory metaclass for each field in the relation considered.
    """
    def __init__(self, name, relation, metadata):
        self.__relation = relation
        self.__name = name
        self.__is_set = False
        self.__metadata = metadata
        self.__sql_type = self.__metadata['fieldtype']
        self.__value = None
        self.__unaccent = False
        self.__comp = '='

    @property
    def _relation(self): # pragma: no cover
        return self.__relation

    @property
    def _metadata(self): # pragma: no cover
        return self.__metadata

    @property
    def py_type(self):
        sql_type = self.__sql_type
        list_ = False
        if sql_type[0] == '_':
            sql_type = sql_type[1:]
            list_ = True
        python_type = SQL_ADAPTER.get(sql_type, typing.Any)
        if list_:
            python_type = typing.List[python_type]
        return python_type

    @property
    def name(self):
        return self.__name

    def is_set(self):
        "Returns if the field is set or not."
        return self.__is_set

    def _is_part_of_pk(self):
        "Returns True if the field is part of the PK"
        return bool(self.__metadata['pkey'])

    def _fieldnum(self):
        return self.__metadata['fieldnum']

    def _pkeynum(self):
        return self.__metadata['pkeynum']

    def _is_unique(self):
        "Returns True if the field is unique"
        return self.__metadata['uniq']

    def is_not_null(self):
        "Returns True if the field is defined as not null."
        return bool(self.__metadata['notnull'])

    def __repr__(self):
        md_ = self.__metadata
        field_constraint = f"{md_['notnull'] and 'NOT NULL' or ''}"
        repr_ = f"({md_['fieldtype']}) {field_constraint}"
        if self.__is_set:
            repr_ = f"{repr_} ({self.__name} {self.__comp} {self.__value})"
        return repr_.strip()

    def __str__(self):
        return str(self.__value)

    def __praf(self, query, ho_id):
        """Returns field_name prefixed with relation alias if the query is
        select. Otherwise, returns the field name quoted with ".
        """
        ho_id = f'r{ho_id}'
        if query == 'select':
            return f'{ho_id}."{self.__name}"'
        return f'"{self.__name}"'

    def _where_repr(self, query, ho_id):
        """Returns the SQL representation of the field for the where clause
        """
        where_repr = ''
        comp_str = '%s'
        isiterable = type(self.__value) in {tuple, list, set}
        col_is_array = self.__sql_type[0] == '_'
        comp = self._comp()
        if comp == '=' and isiterable:
            comp = 'in'
        cast = ''
        if self.__value != NULL and not isiterable:
            cast = f'::{self.__sql_type}'
        if col_is_array and comp == '=':
            where_repr = f'{comp_str} = ANY({self.__praf(query, ho_id)})'
        elif not self.unaccent:
            where_repr = f"{self.__praf(query, ho_id)} {comp} {comp_str}{cast}"
        else:
            where_repr = f"unaccent({self.__praf(query, ho_id)}) {comp} unaccent({comp_str}{cast})"
        return where_repr

    def _where_expr(self, query, ho_id):
        """Returns a FieldExpr AST node for this field's WHERE condition."""
        comp_str = '%s'
        isiterable = type(self.__value) in {tuple, list, set}
        col_is_array = self.__sql_type[0] == '_'
        comp = self._comp()
        if comp == '=' and isiterable:
            comp = 'in'
        is_array_any = col_is_array and comp == '='
        cast = ''
        if not is_array_any and self.__value != NULL and not isiterable:
            cast = f'::{self.__sql_type}'
        return FieldExpr(
            column=self.__praf(query, ho_id),
            comp=comp,
            placeholder=f'{comp_str}{cast}',
            value=self,
            unaccent=self.unaccent,
            array_any=is_array_any,
        )

    @property
    def value(self):
        "Returns the value of the field object"
        return self.__value

    def set(self, *args, unaccent:bool=False):
        """Sets the value (and the comparator) associated with the field."""
        self.__relation._ho_is_singleton = False
        value = args[0]
        if value is None:
            self.__is_set = False
            self.__value = None
            self.__comp = '='
            self.__unaccent = False
            return
        self.__unaccent = unaccent
        comp = None
        if isinstance(value, tuple):
            if len(value) != 2:
                raise ValueError(f"Can't match {value} with (comp, value)!")
            comp, value = value
        if value is None:
            raise ValueError("Can't have a None value with a comparator!")
        if value is NULL and comp is None:
            comp = 'is'
        elif comp is None:
            comp = '='
        if isinstance(value, (list, set)):
            value = tuple(value)
        comp = comp.lower()
        if value is NULL and comp not in {'is', 'is not'}:
            raise ValueError("comp should be 'is' or 'is not' with NULL value!")
        self.__is_set = True
        self.__value = value
        self.__comp = comp

    def _set(self, *args):
        sys.stderr.write(
            "WARNING! Field._set method is deprecated. Use Field.set instead.\n"
            "It will be remove in 1.0 version.\n")
        return self.set(*args)

    def _unset(self): #pragma: no cover
        "Unset a field"
        sys.stderr.write(
            "WARNING! Field._unset method is deprecated. Set the value of the field to None instead.\n"
            "It will be remove in 1.0 version.\n")
        self.__is_set = False
        self.__value = None
        self.__comp = '='

    @property
    def unaccent(self):
        return self.__unaccent
    @unaccent.setter
    def unaccent(self, value):
        if not isinstance(value, bool):
            raise RuntimeError('unaccent value must be True or False!')
        self.__unaccent = value

    def _comp(self):
        "Returns the comparator associated to the value."
        if self.__comp == '%':
            return '%%'
        return self.__comp

    @property
    def _relation(self):
        """Internal usage.

        Returns:
            Relation: The Relation class for which self is an attribute.
        """
        return self.__relation

    def _psycopg_adapter(self):
        """Return the value to be adapted by psycopg."""
        return self.__value

    @property
    def _name(self):
        return self.__name

    def __call__(self):
        """In case someone inadvertently uses the name of a field for a method."""
        rel_class = self.__relation.__class__
        rcn = rel_class.__name__
        method = rel_class.__dict__.get(self.__name)
        err_msg = "'Field' object is not callable."
        warn_msg = f"'{self.__name}' is an attribute of type Field of the '{rcn}' object."
        if method:
            err_msg = f"{err_msg}\n{warn_msg}"
            err_msg = f"{err_msg}\nDo not use '{self.__name}' as a method name."
        raise TypeError(err_msg)

