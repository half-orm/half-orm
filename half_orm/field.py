#-*- coding: utf-8 -*-
# pylint: disable=protected-access

"""This module provides the Field class. It is used by the `relation <#module-half_orm.relation>`_ module."""

import re
import sys
import typing
import warnings
import yaml
from collections.abc import Iterable
from half_orm.null import NULL
from half_orm.sql_adapter import SQL_ADAPTER
from half_orm.sql_ast import FieldExpr


_TEXT_LIKE_TYPES = {'text', 'varchar', 'character varying', 'char', 'bpchar', 'name', 'citext'}


def is_text_like_sql_type(sql_type: str) -> bool:
    """True if `sql_type` (a PostgreSQL type name, e.g. from ho_meta()'s
    per-field 'sql_type') is one ``ilike``/``unaccent`` make sense against.

    Array types (leading ``_``, e.g. ``_text``) are unwrapped first. Used by
    :attr:`Field._is_text_like` internally, and by callers outside this
    module (e.g. half_orm_gen's search) that need the same "is this a text
    type" judgment before choosing a comparator, without duplicating the
    type list.
    """
    return sql_type.lstrip('_') in _TEXT_LIKE_TYPES

# (comparator, column_sql_type) -> right-hand-side SQL template (with a single
# '%s' bind placeholder), used instead of the default "cast the bound value to
# the column's own type" behavior. Needed whenever a PostgreSQL operator's
# right operand isn't of the same type as the left (column) operand — e.g.
# `tsvector @@ tsquery`, not `tsvector @@ tsvector` — so a bare `%s::sql_type`
# cast would be wrong (or, for tsquery specifically, would reject a plain
# multi-word search string since the tsquery input parser requires explicit
# &/|/! operators between lexemes; plainto_tsquery() builds a valid tsquery
# from free text instead).
_OPERATOR_RHS_TEMPLATES = {
    ('@@', 'tsvector'): 'plainto_tsquery(%s)',
}


class Expr:
    """A raw SQL expression for use with :meth:`Field.set`.

    Quoted column identifiers (``"col"``) are automatically prefixed with
    the relation alias in SELECT queries.  String literals use single quotes
    in SQL, so double-quoted tokens are unambiguously column references.

    Use this when you need arithmetic or any SQL expression that
    column-to-column :meth:`Field.set` cannot express::

        from half_orm.field import Expr

        p = Post()
        p.views.set(('>=', Expr('2 * "likes"')))       # views >= 2 * likes
        p.score.set(Expr('"likes" * 10 + "views"'))    # score = likes*10 + views
    """

    def __init__(self, sql: str):
        self.sql = sql

    def _render(self, query, ho_id):
        """Return the SQL fragment, prefixing quoted identifiers with the table alias."""
        if query != 'select':
            return self.sql
        alias = f'r{ho_id}'
        return re.sub(r'"([^"]+)"', lambda m: f'{alias}."{m.group(1)}"', self.sql)

class Field():
    """A column attribute on a :class:`~half_orm.relation.Relation`.

    ``Field`` instances are created automatically for every column in the
    relation.  They are exposed as attributes on relation instances and used
    in two ways:

    * **Read** — inspect the current constraint value or schema metadata
      (``field.value``, ``field.name``, ``field.py_type``, ``field.is_set()``,
      ``field.is_not_null()``).
    * **Write** — constrain the field to filter rows
      (``field.set(value)``, ``field.set((comp, value))``).

    Constraints are set via keyword arguments when instantiating a relation,
    or directly via :meth:`set`:

    .. code-block:: python

        # Equivalent ways to constrain last_name
        Author(last_name='Martin')

        author = Author()
        author.last_name.set('Martin')

    Column-to-column and arithmetic comparisons (same relation instance) are
    supported by passing a sibling ``Field`` or an :class:`Expr`::

        post = Post()
        post.views.set(post.likes)                        # WHERE views = likes
        post.views.set(('>', post.likes))                 # WHERE views > likes
        post.views.set(('>=', Expr('2 * "likes"')))      # WHERE views >= 2 * likes

    Setting a field to ``None`` removes the constraint.
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
        self.__json_schema = self.__parse_json_schema()

    @property
    def _relation(self): # pragma: no cover
        return self.__relation

    @property
    def _metadata(self): # pragma: no cover
        return self.__metadata

    @property
    def py_type(self):
        """The Python type that maps to this column's SQL type.

        Array columns (PostgreSQL ``_type``) are returned as
        ``typing.List[inner_type]``.  Unknown SQL types fall back to
        ``typing.Any``.

        Example::

            Author().last_name.py_type   # <class 'str'>
            Post().tags.py_type          # typing.List[str]  (if tags is text[])
        """
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
        """The column name as it appears in the database."""
        return self.__name

    def is_set(self):
        """Return ``True`` if this field currently carries a constraint.

        A field is *set* after a call to :meth:`set` with a non-``None``
        value, or when the relation was instantiated with a keyword argument
        for this column.  Setting the value back to ``None`` clears the
        constraint.

        Example::

            a = Author()
            a.last_name.is_set()              # False
            a.last_name.set('Martin')
            a.last_name.is_set()              # True
            a.last_name.set(None)
            a.last_name.is_set()              # False
        """
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
        """Return ``True`` if the column is declared ``NOT NULL`` in the schema.

        This reflects the database constraint, not the current value.

        Example::

            Author().last_name.is_not_null()   # True  (declared NOT NULL)
            Author().email.is_not_null()       # True
            Post().content.is_not_null()       # False (nullable column)
        """
        return bool(self.__metadata['notnull'])

    @property
    def has_default_value(self):
        """The default expression for this column, or ``None`` if there is none.

        Returns the PostgreSQL expression string as stored in ``pg_attrdef``,
        e.g. ``"nextval('seq'::regclass)"``, ``"'active'::text"``, ``"now()"``.

        Example::

            Author().id.has_default_value        # "nextval('author_id_seq'::regclass)"
            Author().last_name.has_default_value # None
        """
        return self.__metadata.get('default_expr')

    def __parse_json_schema(self):
        desc = self.__metadata.get('fielddescription') or ''
        m = re.search(r'@json\s*```yaml\s*(.*?)(?:```|\Z)', desc, re.DOTALL)
        if not m:
            return None
        try:
            return yaml.safe_load(m.group(1))
        except yaml.YAMLError:
            return None

    @property
    def json_schema(self):
        """Parsed structure from the ``@json`` block in the column comment, or ``None``.

        Returns the YAML structure as a Python object (dict/list/str) when the
        column comment contains an ``@json`` block::

            @json
            ```yaml
            lang: text          # ISO 639-1
            views: integer
            tags: [text]
            items:
              - id: uuid
                name: text
            ```

        Returns ``None`` when no ``@json`` block is present.
        """
        return self.__json_schema

    def __repr__(self):
        md_ = self.__metadata
        field_constraint = f"{md_['notnull'] and 'NOT NULL' or ''}"
        repr_ = f"({md_['fieldtype']}) {field_constraint}"
        if self.__is_set:
            repr_ = f"{repr_} ({self.__name} {self.__comp} {self.__value})"
        repr_ = repr_.strip()
        if self.__json_schema is not None:
            yaml_str = yaml.dump(self.__json_schema, default_flow_style=False, allow_unicode=True)
            for line in yaml_str.rstrip('\n').splitlines():
                repr_ += f'\n    {line}'
        return repr_

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
        rhs = _OPERATOR_RHS_TEMPLATES.get((comp, self.__sql_type), f'{comp_str}{cast}')
        if col_is_array and comp == '=':
            where_repr = f'{comp_str} = ANY({self.__praf(query, ho_id)})'
        elif not self.unaccent or not self._is_text_like:
            where_repr = f"{self.__praf(query, ho_id)} {comp} {rhs}"
        else:
            where_repr = f"unaccent({self.__praf(query, ho_id)}) {comp} unaccent({rhs})"
        return where_repr

    def _where_expr(self, query, ho_id):
        """Returns a FieldExpr AST node for this field's WHERE condition."""
        comp_str = '%s'
        # Expr (raw SQL expression): emit rendered fragment, no bound parameter
        if isinstance(self.__value, Expr):
            return FieldExpr(
                column=self.__praf(query, ho_id),
                comp=self._comp(),
                placeholder='',
                value=None,
                col_ref=self.__value._render(query, ho_id),
            )
        # Field-to-field: emit column reference, no bound parameter
        if isinstance(self.__value, Field):
            target = self.__value
            target_ho_id = target._relation.ho_id
            col_ref = target.__praf(query, target_ho_id)
            return FieldExpr(
                column=self.__praf(query, ho_id),
                comp=self._comp(),
                placeholder='',
                value=None,
                col_ref=col_ref,
            )
        isiterable = type(self.__value) in {tuple, list, set}
        col_is_array = self.__sql_type[0] == '_'
        comp = self._comp()
        if comp == '=' and isiterable:
            comp = 'in'
        is_array_any = col_is_array and comp == '='
        cast = ''
        if not is_array_any and self.__value != NULL and not isiterable:
            cast = f'::{self.__sql_type}'
        placeholder = _OPERATOR_RHS_TEMPLATES.get((comp, self.__sql_type), f'{comp_str}{cast}')
        return FieldExpr(
            column=self.__praf(query, ho_id),
            comp=comp,
            placeholder=placeholder,
            value=self,
            unaccent=self.unaccent and self._is_text_like,
            array_any=is_array_any,
        )

    @property
    def value(self):
        """The current constraint value, or ``None`` if the field is not set.

        Use this to read back a value that was set on a row returned by
        :meth:`~half_orm.relation.Relation.ho_get` or extracted from an
        :meth:`~half_orm.relation.Relation.ho_select` result::

            author = Author(last_name='Martin').ho_get()
            author.last_name.value    # 'Martin'
            author.first_name.value   # 'Alice'
        """
        return self.__value

    def set(self, *args, unaccent:bool=False):
        """Constrain this field, optionally with a custom comparator.

        Parameters
        ----------
        value :
            The constraint value.  Pass ``None`` to *remove* the constraint.
            Pass a ``(comparator, value)`` tuple to use an operator other than
            ``=``.  Supported comparators: ``=``, ``!=``, ``<``, ``<=``,
            ``>``, ``>=``, ``like``, ``ilike``, ``in``, ``is``, ``is not``,
            and any other PostgreSQL operator accepted in a WHERE clause.

            Pass a sibling ``Field`` of the **same** relation instance, or an
            :class:`Expr` for arbitrary SQL expressions, to compare columns of
            the same table without bound parameters.

        unaccent : bool
            When ``True``, wraps both sides in PostgreSQL ``unaccent()``
            before comparing.  Requires the ``unaccent`` extension.

        Examples::

            a = Author()
            a.last_name.set('Martin')               # last_name = 'Martin'
            a.last_name.set(('ilike', 'mar%'))       # last_name ILIKE 'mar%'
            a.last_name.set(('ilike', 'mar%'), unaccent=True)
                                                    # unaccent(last_name) ILIKE unaccent('mar%')

            from half_orm.null import NULL
            a.last_name.set(NULL)                   # last_name IS NULL
            a.last_name.set(('is not', NULL))        # last_name IS NOT NULL

            a.last_name.set(None)                   # removes the constraint

            # Column-to-column (same relation instance)
            p = Post()
            p.views.set(p.likes)                              # views = likes
            p.views.set(('>', p.likes))                       # views > likes

            # Arbitrary SQL expression
            from half_orm.field import Expr
            p.views.set(('>=', Expr('2 * "likes"')))          # views >= 2 * likes
            p.score.set(Expr('"likes" * 10 + "views"'))       # score = likes*10 + views
        """
        self.__relation._ho_is_singleton = False
        value = args[0]
        if value is None:
            self.__is_set = False
            self.__value = None
            self.__comp = '='
            self.__unaccent = False
            return
        self.unaccent = unaccent
        comp = None
        if isinstance(value, tuple):
            if len(value) != 2:
                raise ValueError(f"Can't match {value} with (comp, value)!")
            comp, value = value
        if value is None:
            raise ValueError("Can't have a None value with a comparator!")
        # Expr (raw SQL expression)
        if isinstance(value, Expr):
            self.__is_set = True
            self.__value = value
            self.__comp = comp or '='
            return
        # Field-to-field comparison (same relation instance → col-ref)
        if isinstance(value, Field):
            if value.__relation is self.__relation:
                # Same relation: store the Field for column-to-column SQL
                self.__is_set = True
                self.__value = value
                self.__comp = comp or '='
                return
            else:
                # Different relation instance: extract the scalar value
                value = value.value
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
        """Whether ``unaccent()`` is applied to this field's comparison.

        Can also be set via the ``unaccent`` keyword argument of :meth:`set`.
        Requires the PostgreSQL ``unaccent`` extension to be installed.
        """
        return self.__unaccent

    @property
    def _is_text_like(self):
        return is_text_like_sql_type(self.__sql_type)

    @unaccent.setter
    def unaccent(self, value):
        if not isinstance(value, bool):
            raise RuntimeError('unaccent value must be True or False!')
        if value and not self._is_text_like:
            warnings.warn(
                f"unaccent ignored: field '{self.__name}' has non-text type '{self.__sql_type}'",
                UserWarning,
                stacklevel=2,
            )
            value = False
        if value and not self.__relation._ho_model.has_extension('unaccent'):
            warnings.warn(
                f"unaccent ignored: the \"unaccent\" PostgreSQL extension is not "
                f"installed on database '{self.__relation._ho_model._dbname}'. "
                f"Install it with: CREATE EXTENSION IF NOT EXISTS unaccent;",
                UserWarning,
                stacklevel=2,
            )
            value = False
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

