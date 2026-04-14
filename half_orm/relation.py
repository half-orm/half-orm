#-*- coding: utf-8 -*-
# pylint: disable=protected-access, too-few-public-methods, no-member

"""Core predicate/relation abstraction for halfORM.

A :class:`Relation` object is a **predicate** — it describes the logical
condition that rows must satisfy to belong to the relation. Its *extension*
is the set of rows currently satisfying that predicate in the database.

This module is used by :mod:`half_orm.model` to generate relation classes
via :meth:`~half_orm.model.Model.get_relation_class`. It also provides the
:func:`singleton` and :func:`transaction` decorators for use in custom
subclasses.

Example:
    >>> from half_orm.model import Model
    >>> blog = Model('blog')
    >>> Author = blog.get_relation_class('blog.author')
    >>> Author(last_name='Martin').ho_count()   # cardinality of the predicate
    3
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
    CompoundSelect as ASTCompoundSelect,
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
    """Stub for IDE type-checking only. See :class:`Relation` for full documentation."""
    def __init__(self, **kwargs): ...

    def ho_insert(self, *args) -> Dict:
        """Insert the row described by this predicate. Returns the inserted row as a dict. *Executes SQL.*"""
        ...
    def ho_select(self, *args,
        distinct:bool=False, order_by:str=None, limit:int=None, offset:int=None,
        json_agg=None):
        """Enumerate the extension of this predicate. Generator yielding one dict per row. *Executes SQL.*"""
        ...
    def ho_update(self, *args, update_all=False, **kwargs) -> Optional[Dict]:
        """Update every row that satisfies the predicate. *Executes SQL.*"""
        ...
    def ho_delete(self, *args, delete_all=False):
        """Remove every row that satisfies the predicate. *Executes SQL.*"""
        ...
    def ho_assert_is_singleton(self):
        """Assert that this predicate identifies exactly one row, without querying the database."""
        ...
    def ho_get(self, *args) -> dict:
        """Fetch the single row matching this predicate from the database. *Executes SQL.*"""
        ...
    def ho_is_set(self) -> bool:
        """Return True if at least one field or FK constraint is set."""
        ...
    def ho_mogrify(self):
        """Print the SQL SELECT that would be executed and return self."""
        ...
    def ho_unaccent(self, *fields_names) -> 'Relation':
        """Apply unaccent to the listed fields for the next SELECT."""
        ...
    def ho_count(self, *args, distinct:bool=False) -> int:
        """Return the number of rows that satisfy the predicate. *Executes SQL.*"""
        ...
    def ho_is_empty(self) -> bool:
        """Return True if the extension is empty, False otherwise. *Executes SQL.*"""
        ...
    async def ho_ainsert(self, *args) -> dict:
        """Async variant of ho_insert. *Executes SQL.*"""
        ...
    async def ho_aget(self, *args) -> dict:
        """Async variant of ho_get. *Executes SQL.*"""
        ...
    async def ho_aselect(self, *args,
        distinct:bool=False, order_by:str=None, limit:int=None, offset:int=None):
        """Async variant of ho_select. Returns a list of dicts. *Executes SQL.*"""
        ...
    async def ho_aupdate(self, *args, update_all=False, **kwargs):
        """Async variant of ho_update. *Executes SQL.*"""
        ...
    async def ho_adelete(self, *args, delete_all=False):
        """Async variant of ho_delete. *Executes SQL.*"""
        ...
    async def ho_acount(self, *args, distinct:bool=False) -> int:
        """Async variant of ho_count. *Executes SQL.*"""
        ...
    async def ho_ais_empty(self) -> bool:
        """Async variant of ho_is_empty. *Executes SQL.*"""
        ...
    @classmethod
    def ho_copy(cls, data, columns=None) -> int:
        """Load rows using PostgreSQL COPY FROM. Returns the number of inserted rows. *Executes SQL.*"""
        ...
    @classmethod
    async def ho_acopy(cls, data, columns=None) -> int:
        """Async variant of ho_copy. *Executes SQL.*"""
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
        self._ho_fields = {}
        self._ho_fields_by_fieldnum = {}
        self._ho_pkey = {}
        self._ho_ukeys = []
        self._ho_fkeys = OrderedDict()
        self._ho_fkeys_attr = set()
        self._ho_join_to = {}
        self._ho_union_branches = None   # set by __or__ when FK joins require UNION
        self._ho_except_branches = None  # set by __sub__ when FK joins require EXCEPT
        self._ho_is_singleton = False
        self._ho_only = False
        self._ho_neg = False
        self._ho_set_fields()
        self._ho_set_fkeys()
        self._ho_query = ""
        self._ho_query_type = None
        self._ho_ast_joins = []
        self._ho_set_operators = _SetOperators(self)

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
        """Insert the row described by this predicate. *Executes SQL.*

        Args:
            *args: column names to include in the returned dict. If omitted,
                all columns are returned (equivalent to ``RETURNING *``).

        Returns:
            dict: the inserted row.

        Raises:
            ReadOnlyRelationError: if the relation is a view or other
                non-writable kind.

        Example:
            Insert an author:
                ```python
                alice = Author(
                    first_name='Alice', last_name='Martin',
                    email='alice@example.com',
                ).ho_insert()
                alice['id']   # 1
                ```
        """
        query, vals = self._ho_prep_insert(*args)
        with self.__execute(query, vals) as cursor:
            res = cursor.fetchall() or [{}]
            return res[0]

    @classmethod
    def ho_copy(cls, data, columns=None) -> int:
        """Load rows into the table using PostgreSQL ``COPY FROM``. *Executes SQL.*

        Much faster than repeated :meth:`ho_insert` calls for bulk loads.
        No ``RETURNING`` is supported — the number of inserted rows is returned
        instead.

        *New in version 0.18.12.*

        Args:
            data: either a ``list[dict]`` (column names are taken from the keys
                of the first dict) or a file-like object opened in text mode
                (CSV with a header row, or headerless if ``columns`` is given).
            columns (list[str] | None): explicit column list. Required when
                *data* is a headerless file-like object; ignored when *data* is
                a ``list[dict]``.

        Returns:
            int: number of rows inserted.

        Raises:
            ReadOnlyRelationError: if the relation is a view or other
                non-writable kind.
            ValueError: if *data* is empty or *columns* is required but missing.

        Example:
            From a list of dicts:
                ```python
                n = Author.ho_copy([
                    {'first_name': 'Bob', 'last_name': 'Martin',
                     'birth_date': date(1980, 1, 1)},
                    {'first_name': 'Eve', 'last_name': 'Dupont',
                     'birth_date': date(1990, 5, 12)},
                ])
                print(n)  # 2
                ```

            From a CSV file (with header row):
                ```python
                with open('authors.csv') as f:
                    n = Author.ho_copy(f)
                ```

            From a headerless CSV file:
                ```python
                with open('authors_no_header.csv') as f:
                    n = Author.ho_copy(
                        f,
                        columns=['first_name', 'last_name', 'birth_date'],
                    )
                ```
        """
        cls()._ho_check_writable()
        conn = cls._ho_model._connection
        if hasattr(data, 'read'):
            # File-like object — stream CSV directly into COPY
            if columns is None:
                # First line is the header
                header = data.readline().rstrip('\n')
                columns = [c.strip() for c in header.split(',')]
            cols = ', '.join(f'"{c}"' for c in columns)
            stmt = f'copy {cls._qrn} ({cols}) from stdin (format csv)'
            count = 0
            with conn.cursor().copy(stmt) as copy:
                for line in data:
                    copy.write(line)
                    count += 1
            return count
        else:
            # list[dict]
            if not data:
                raise ValueError('ho_copy: data must not be empty')
            columns = list(data[0].keys())
            cols = ', '.join(f'"{c}"' for c in columns)
            stmt = f'copy {cls._qrn} ({cols}) from stdin'
            with conn.cursor().copy(stmt) as copy:
                for row in data:
                    copy.write_row([row[c] for c in columns])
            return len(data)

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
        distinct = 'distinct' if distinct else ''
        can_dedup = bool(self._ho_join_to) and self._ho_result_is_relation(*args)
        pk_names = list(self._ho_pkey.keys())
        query, values = self._ho_prep_select(
            *args, distinct=distinct, order_by=order_by, limit=limit, offset=offset)
        return query, values, can_dedup, pk_names

    def ho_select(self, *args,
        distinct:bool=False, order_by:str=None, limit:int=None, offset: int=None,
        json_agg=None):
        """Enumerate the extension of this predicate. *Executes SQL.*

        This method is a generator. Without arguments it is equivalent to
        iterating directly on the relation object (``for row in rel:``).

        Args:
            *args: column names to project. If omitted, all columns are
                returned.
            distinct (bool): add ``DISTINCT`` to the SELECT. Default: ``False``.
            order_by (str): SQL ``ORDER BY`` clause, e.g.
                ``'last_name, first_name desc'``. Default: ``None``.
            limit (int): maximum number of rows to return. Default: ``None``.
            offset (int): number of rows to skip. Default: ``None``.
            json_agg (dict): aggregate already-set fkeys as JSON arrays via
                a ``LEFT JOIN`` + ``json_agg`` + ``GROUP BY`` on the primary key.

                Each entry maps a fkey attribute name to its spec:

                - ``[field, ...]`` — list of column names; alias = fkey attr name.
                - ``{'fields': [...], 'alias': 'name'}`` — explicit alias.
                - ``[]`` — empty list returns all columns via ``row_to_json``.

                The fkey must have been set via ``.fk_attr.set(rel)`` before
                calling ``ho_select``.

                The type of the aggregated value depends on the FK direction:

                - **reverse FK, non-unique** (one-to-many): a ``list`` of dicts,
                  empty (``[]``) when no related rows exist.
                - **reverse FK, unique** (one-to-one via UNIQUE or PK constraint):
                  a single ``dict``, or ``None`` when no related row exists.
                - **direct FK** (many-to-one): a single ``dict``, or ``None``
                  when the FK target is absent (nullable FK).

        Yields:
            dict: one row of the extension.

        Example:
            Project and sort:
                ```python
                for row in Author(last_name='Martin').ho_select('id', 'email', order_by='id'):
                    print(row)   # {'id': 1, 'email': 'alice@example.com'}
                ```

            Aggregate related rows as JSON (reverse FK):
                ```python
                alice = Author(last_name='Martin')
                alice.post_rfk.set()   # join all posts
                for row in alice.ho_select(json_agg={'post_rfk': ['id', 'title']}):
                    print(row['post_rfk'])  # [{'id': 1, 'title': '...'}, ...]
                ```

            Chained FK (A ← B → C) — aggregate the leaf relation's data:
                ```python
                # For each post, collect the persons who commented on it.
                # post ← comment → person  (comment is the junction)
                post = Post(title='Hello')
                comment = Comment()
                comment.author_fk.set()   # chain: comment → person
                post.comment_rfk.set(comment)
                for row in post.ho_select(json_agg={'comment_rfk': ['last_name']}):
                    print(row['comment_rfk'])  # [{'last_name': '...'}, ...]
                ```

        *New in version 0.18.0:* ``distinct``, ``order_by``, ``limit`` and ``offset`` parameters.

        *New in version 0.18.6:* ``json_agg`` parameter.

        *Changed in version 0.18.7* **(breaking)**: direct FK and singleton reverse FK (UNIQUE/PK) in ``json_agg`` return a ``dict`` (or ``None``) instead of a list.
        """
        if json_agg is not None:
            query, values = self._ho_prep_json_agg_select(
                *args, json_agg=json_agg, order_by=order_by, limit=limit, offset=offset)
            with self.__execute(query, values) as cursor:
                yield from cursor
            return
        query, values, can_dedup, pk_names = self._ho_prep_select_query(
            *args, distinct=distinct, order_by=order_by, limit=limit, offset=offset)
        seen = set()
        dup_count = 0
        try:
            with self.__execute(query, values) as cursor:
                for elt in cursor:
                    row = elt
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
        """Assert that this predicate identifies exactly one row, without querying the database.

        A predicate is a *singleton* when:

        * every field of a unique identifier (primary key or any
          ``UNIQUE NOT NULL`` constraint) is set with the ``=`` comparator, **or**
        * a FK join constrains a unique identifier of this relation: the fields
          on *this* side of the join form a PK or UNIQUE NOT NULL, and the
          corresponding fields on the joined relation are all fixed with ``=``.

        The check is purely structural — no SQL is executed.

        Returns:
            self — for chaining before a write operation.

        Raises:
            NotASingletonError: if no unique identifier is fully set.

        Example:
            ho_is_singleton usage:
                ```python
                # OK — id is the primary key
                Author(id=42).ho_assert_is_singleton()

                # OK — email has a UNIQUE NOT NULL constraint
                Author(email='alice@example.com').ho_assert_is_singleton()

                # Raises — last_name is not a unique identifier
                Author(last_name='Martin').ho_assert_is_singleton()

                # OK — FK navigation: comment.post_id fixes post.id (PK)
                Comment(post_id=42).fk_post().ho_assert_is_singleton()

                # Typical usage: guard a single-row write
                Author(id=42).ho_assert_is_singleton().ho_update(email='new@example.com')

                # Via FK navigation: delete the post linked to a specific comment
                Comment(post_id=42).fk_post().ho_assert_is_singleton().ho_delete()
                ```

        *New in version 0.18.0.*
        """
        def _fully_set(fields):
            return all(f.is_set() and f._comp() == '=' for f in fields.values())

        if self._ho_pkey and _fully_set(self._ho_pkey):
            return self
        for ukey in self._ho_ukeys:
            if _fully_set(ukey):
                return self
        # A FK join uniquely identifies self when:
        #   - the fields on self involved in the join form a PK or UNIQUE NOT NULL, AND
        #   - the corresponding fields on the joined relation are all fixed with '='.
        def _all_eq(names, rel):
            return all(
                rel._ho_fields.get(n.strip('"')) is not None
                and rel._ho_fields[n.strip('"')].is_set()
                and rel._ho_fields[n.strip('"')]._comp() == '='
                for n in names
            )
        for fkey, fk_rel in self._ho_join_to.items():
            self_fields = frozenset(fkey.names)
            on_pk = bool(self._ho_pkey) and self_fields == frozenset(self._ho_pkey.keys())
            on_ukey = any(self_fields == frozenset(uk.keys()) for uk in self._ho_ukeys)
            if (on_pk or on_ukey) and _all_eq(fkey.fk_names, fk_rel):
                return self
        if not self._ho_pkey and not self._ho_ukeys:
            raise relation_errors.NotASingletonError(
                f"{self.__class__.__name__} has no primary key or unique NOT NULL constraint.")
        raise relation_errors.NotASingletonError(
            f"No unique identifier fully set with '=' on {self.__class__.__name__}.")

    #@utils.trace
    def ho_get(self, *args: str) -> dict:
        """Fetch the single row matching this predicate from the database. *Executes SQL.*

        Guarantees that the predicate matches exactly one row and returns it as
        a plain ``dict`` mapping column names to their Python values.
        Issues a single ``SELECT … LIMIT 2`` query.

        Args:
            *args: optional column names to select.  If omitted, all columns
                are returned.

        Returns:
            dict: the matching row.

        Raises:
            NotFoundError: no row matches the predicate.
            MultipleRowsError: more than one row matches the predicate.

        Example:
            ho_get usage:
                ```python
                row = Person(last_name='Lagaffe', first_name='Gaston').ho_get()
                print(row['id'], row['last_name'])
                ```

        *Changed in version 1.0.0* **(breaking)**: returns a ``dict`` instead
        of a ``Relation`` object.  Raises :exc:`NotFoundError` or
        :exc:`MultipleRowsError` instead of the generic :exc:`ExpectedOneError`.
        """
        self._ho_check_colums(*args)
        rows = list(self.ho_select(*args, limit=2))
        if len(rows) == 0:
            raise relation_errors.NotFoundError(self)
        if len(rows) > 1:
            raise relation_errors.MultipleRowsError(self)
        return rows[0]

    async def ho_aget(self, *args: str) -> dict:
        """Async variant of ho_get. *Executes SQL.*

        Issues a single ``SELECT … LIMIT 2`` query and returns the matching
        row as a plain ``dict``.

        Args:
            *args: optional column names to select.  If omitted, all columns
                are returned.

        Returns:
            dict: the matching row.

        Raises:
            NotFoundError: no row matches the predicate.
            MultipleRowsError: more than one row matches the predicate.

        *New in version 1.0.0.*
        """
        self._ho_check_colums(*args)
        rows = await self.ho_aselect(*args, limit=2)
        if len(rows) == 0:
            raise relation_errors.NotFoundError(self)
        if len(rows) > 1:
            raise relation_errors.MultipleRowsError(self)
        return rows[0]

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
        set_clause = []
        for field_name, new_value in update_args.items():
            col_name = self._ho_fields[field_name].name
            set_clause.append((f'"{col_name}" = %s', new_value))
        if self._ho_join_to:
            # Build a subquery to avoid any DB round-trip and to correctly
            # propagate JOIN constraints into the UPDATE predicate.
            pk_names = list(self._ho_pkey.keys())
            sub_sql, sub_vals = self._ho_prep_select(*pk_names)
            if len(pk_names) == 1:
                where = ASTRaw(f'"{pk_names[0]}" in ({sub_sql})', sub_vals)
            else:
                pk_cols = ', '.join(f'"{pk}"' for pk in pk_names)
                where = ASTRaw(f'({pk_cols}) in ({sub_sql})', sub_vals)
            stmt = ASTUpdate(
                table=self._qrn,
                set_clause=set_clause,
                where=where,
                returning=ASTReturning(list(args)) if args else None,
            )
        else:
            _, where_expr = self.__where_args()
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
        """Update every row that satisfies the predicate. *Executes SQL.*

        Args:
            *args: column names to return from the updated rows. Pass
                ``'*'`` to return all columns. If omitted, nothing is returned.
            update_all (bool): must be ``True`` when ``self`` has no
                constraint set, to confirm the intent to update all rows.
                Default: ``False``.
            **kwargs: ``{column_name: new_value}`` pairs to apply.
                ``None`` values are silently ignored.

        Returns:
            list[dict] | None: the updated rows if ``*args`` was provided,
            otherwise ``None``.

        Raises:
            RuntimeError: if no constraint is set and ``update_all`` is
                ``False``.

        Example:
            ho_update usage:
                ```python
                # Update a single row — guarded by singleton check
                Author(id=1).ho_assert_is_singleton().ho_update(email='new@example.com')

                # Update an entire subset at once
                Post(author_id=99).ho_update(content='[archived]')
                ```
        """
        prep = self._ho_prep_update(*args, update_all=update_all, **kwargs)
        if prep is None:
            return None
        query, vals, update_args = prep
        with self.__execute(query, vals) as cursor:
            for field_name, value in update_args.items():
                self._ho_fields[field_name].set(value)
            if args:
                return cursor.fetchall()
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
        if self._ho_join_to:
            # Build a subquery to avoid any DB round-trip and to correctly
            # propagate JOIN constraints into the DELETE predicate.
            pk_names = list(self._ho_pkey.keys())
            sub_sql, sub_vals = self._ho_prep_select(*pk_names)
            if len(pk_names) == 1:
                where = ASTRaw(f'"{pk_names[0]}" in ({sub_sql})', sub_vals)
            else:
                pk_cols = ', '.join(f'"{pk}"' for pk in pk_names)
                where = ASTRaw(f'({pk_cols}) in ({sub_sql})', sub_vals)
            stmt = ASTDelete(
                table=self._qrn,
                where=where,
                returning=ASTReturning(list(args)) if args else None,
            )
        else:
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
        """Remove every row that satisfies the predicate. *Executes SQL.*

        Args:
            *args: column names to return from the deleted rows. Pass
                ``'*'`` to return all columns.
            delete_all (bool): must be ``True`` when no primary key field
                is set, as a safety guard against accidental mass deletions.
                Default: ``False``.

        Returns:
            list[dict] | None: the deleted rows if ``*args`` was provided,
            otherwise ``None``.

        Raises:
            RuntimeError: if the predicate is not set and ``delete_all``
                is ``False``.

        Example:
            ho_delete usage:
                ```python
                # Delete one identified row
                Author(id=99).ho_assert_is_singleton().ho_delete()

                # Delete all posts for a given author
                Post(author_id=1).ho_delete(delete_all=True)
                ```
        """
        query, vals = self._ho_prep_delete(*args, delete_all=delete_all)
        with self.__execute(query, vals) as cursor:
            if args:
                return cursor.fetchall()
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
        # If no PRIMARY KEY is defined, the first UNIQUE NOT NULL constraint
        # acts as the effective PK (FK references to it are valid in PostgreSQL).
        if not self._ho_pkey and self._ho_ukeys:
            self._ho_pkey = self._ho_ukeys[0]

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

        *New in version 0.18.0.*
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
Foreign keys (direct and reverse) are accessible with the keys of the Fkeys dictionary below.
Copy/paste the Fkeys dictionary and replace the key with the alias you want to use instead.

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
            fkey_to_attr = {}
            for attr_name in self._ho_fkeys_attr:
                fkey_obj = getattr(self, attr_name, None)
                for fkeyname, fkey in self._ho_fkeys.items():
                    if fkey is fkey_obj:
                        fkey_to_attr[fkeyname] = attr_name
                        break
            ret.append(fkeys_usage)
            if hasattr(self, 'Fkeys'):
                for key, value in self.Fkeys.items():
                    fkey_to_attr[value] = key
            for fkey in self._ho_fkeys:
                if fkey in fkey_to_attr: # skip joins
                    ret.append(f"    '{fkey_to_attr[fkey]}': '{fkey}',")
            ret.append('}')
        return '\n'.join(ret)

    def ho_is_set(self):
        """Return True if one field at least is set or if self has been
        constrained by at least one of its foreign keys or self is the
        result of a combination of Relations (using set operators) where
        at least one operand is itself constrained.
        """
        joined_to = any(jt_.ho_is_set() for jt_ in self._ho_join_to.values())
        op = self._ho_set_operators.operator
        if op:
            left_set = self._ho_set_operators.left.ho_is_set()
            right = self._ho_set_operators.right
            right_set = right is not None and right.ho_is_set()
            if op == "or":
                # A() | B → all rows if any operand is unconstrained
                set_op_constrained = left_set and right_set
            else:
                # "and" / "and not": unconstrained operand is transparent
                set_op_constrained = left_set or right_set
        else:
            set_op_constrained = False
        return (joined_to or set_op_constrained or bool(self._ho_neg) or
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

    def _ho_build_select_ast(self, *args,
        distinct: str = '', order_by: str = None,
        limit: int = None, offset: int = None) -> ASTSelect:
        """Build and return an :class:`~half_orm.sql_ast.Select` node.

        This is the counterpart of :meth:`_ho_prep_select` for use in compound
        statements (UNION, EXCEPT) where each branch must remain an independent
        ``Select`` node that :class:`~half_orm.sql_ast.CompoundSelect` can
        assemble.  Callers that only need the final SQL string should use
        :meth:`_ho_prep_select` instead.
        """
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
        seen_tables: set = set()
        unique_joins = []
        for j in self._ho_ast_joins:
            if j.table not in seen_tables:
                seen_tables.add(j.table)
                unique_joins.append(j)

        return ASTSelect(
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

    def _ho_prep_union_select(self, *args,
        distinct: str = '', order_by: str = None,
        limit: int = None, offset: int = None):
        """Generate UNION SQL for ``|`` when FK joins make JOIN+WHERE incorrect.

        Each branch is rendered as an independent :class:`~half_orm.sql_ast.Select`
        node so that incompatible JOIN structures (different FK paths or different
        constraints on the same table) are kept separate.  The branches are
        combined by :class:`~half_orm.sql_ast.CompoundSelect` using ``UNION``
        (which deduplicates rows across branches).
        """
        def collect_branches(rel):
            """Flatten nested UNION trees into a flat list of leaf branches."""
            if rel._ho_union_branches is None:
                return [rel]
            left, right = rel._ho_union_branches
            return collect_branches(left) + collect_branches(right)

        branch_asts = [
            branch._ho_build_select_ast(*args, distinct=distinct)
            for branch in collect_branches(self)
        ]
        return ASTCompoundSelect(
            operator='UNION',
            branches=branch_asts,
            order_by=order_by,
            limit=limit,
            offset=offset,
        ).to_sql()

    def _ho_prep_except_select(self, *args,
        distinct: str = '', order_by: str = None,
        limit: int = None, offset: int = None):
        """Generate EXCEPT SQL for ``-`` when FK joins make JOIN+WHERE incorrect.

        Each side is rendered as an independent :class:`~half_orm.sql_ast.Select`
        node so that incompatible JOIN structures are kept separate.
        :class:`~half_orm.sql_ast.CompoundSelect` assembles them with ``EXCEPT``,
        which eliminates rows of the left branch that appear in the right branch.
        """
        left, right = self._ho_except_branches
        return ASTCompoundSelect(
            operator='EXCEPT',
            branches=[
                left._ho_build_select_ast(*args, distinct=distinct),
                right._ho_build_select_ast(*args, distinct=distinct),
            ],
            order_by=order_by,
            limit=limit,
            offset=offset,
        ).to_sql()

    #@utils.trace
    def _ho_prep_select(self, *args,
        distinct: str = '', order_by: str = None,
        limit: int = None, offset: int = None):

        if self._ho_except_branches is not None:
            return self._ho_prep_except_select(
                *args, distinct=distinct,
                order_by=order_by, limit=limit, offset=offset)

        if self._ho_union_branches is not None:
            return self._ho_prep_union_select(
                *args, distinct=distinct,
                order_by=order_by, limit=limit, offset=offset)

        return self._ho_build_select_ast(
            *args, distinct=distinct,
            order_by=order_by, limit=limit, offset=offset,
        ).to_sql()

    def _ho_prep_json_agg_select(self, *args, json_agg,
        order_by=None, limit=None, offset=None):
        """Prepare a SELECT with LEFT JOIN + json_agg aggregation.

        Parameters
        ----------
        json_agg : dict
            Each entry maps a fkey attribute to its aggregation spec.
            The spec can be:

            * a **list** ``[*fields]``: the fkey attribute name is used as
              the output column name.
            * a **dict** ``{'fields': [...], 'alias': 'name'}``: *alias* is
              optional (defaults to the fkey attribute name); *fields* is an
              optional subset of columns (empty = all fields via row_to_json).
        """
        from half_orm.fkey import FKey

        self._ho_ast_joins = []
        self._ho_query_type = 'select'

        what, where_expr = self.__where_args(*args)
        columns = [what]
        if not self._ho_pkey:
            raise RuntimeError(
                f"ho_select(json_agg=...) requires the main relation to have a primary key "
                f"({self._qrn} has none).")

        # First pass: resolve FKeys, build JOINs, follow FK chains, collect per-entry info.
        # Each entry records (is_list, leaf_rel, alias, obj_expr) where:
        #   is_list  — True when the result should be a JSON array (GROUP BY needed)
        #   leaf_rel — the last relation in the chain (whose columns are aggregated)
        entries = []
        has_reverse = False
        for fkey_attr, spec in json_agg.items():
            if isinstance(spec, dict):
                alias = spec.get('alias', fkey_attr)
                fields = spec.get('fields', [])
            else:
                alias = fkey_attr
                fields = list(spec)

            fkey = self.__dict__.get(fkey_attr)
            if not isinstance(fkey, FKey):
                raise RuntimeError(
                    f"self.{fkey_attr} is not a FKey"
                    + (f" (got {type(fkey).__name__})" if fkey is not None else " (not found)"))

            fk_rel = self._ho_join_to.get(fkey)
            if fk_rel is None:
                raise RuntimeError(
                    f"self.{fkey_attr} has not been set. Call self.{fkey_attr}.set(...) first.")

            # First JOIN: main relation → fk_rel
            fk_rel._ho_query_type = 'select'
            fk_where_expr = fk_rel.__where_expr(fk_rel.ho_id)
            self._ho_ast_joins.append(ASTJoin(
                table=fk_rel._ho_sql_id(),
                on=fkey._join_query(self),
                where=fk_where_expr,
                join_type='left join',
            ))
            is_list = fkey.is_reverse and not fkey.is_singleton

            # Follow chained FKs (e.g. A ← B → C): fk_rel may itself have FKs set.
            leaf_rel = fk_rel
            current_rel = fk_rel
            while current_rel._ho_join_to:
                if len(current_rel._ho_join_to) > 1:
                    raise RuntimeError(
                        f"json_agg: branching FK chains are not supported — "
                        f"{current_rel._qrn} has {len(current_rel._ho_join_to)} FKs set simultaneously.")
                chained_fkey, chained_rel = next(iter(current_rel._ho_join_to.items()))
                chained_rel._ho_query_type = 'select'
                chained_where = chained_rel.__where_expr(chained_rel.ho_id)
                self._ho_ast_joins.append(ASTJoin(
                    table=chained_rel._ho_sql_id(),
                    on=chained_fkey._join_query(self),
                    where=chained_where,
                    join_type='left join',
                ))
                if chained_fkey.is_reverse and not chained_fkey.is_singleton:
                    is_list = True
                leaf_rel = chained_rel
                current_rel = chained_rel

            rel_id = f'r{leaf_rel.ho_id}'
            if fields:
                obj_pairs = ', '.join(f"'{f}', {rel_id}.\"{f}\"" for f in fields)
                obj_expr = f'json_build_object({obj_pairs})'
            else:
                obj_expr = f'row_to_json({rel_id})'

            if is_list:
                has_reverse = True
            entries.append((is_list, leaf_rel, alias, obj_expr))

        # Second pass: build column expressions.
        # GROUP BY is required only when at least one entry produces a list.
        # Scalar entries (dict/None) need special treatment when GROUP BY is present.
        for is_list, leaf_rel, alias, obj_expr in entries:
            is_scalar = not is_list
            if not is_scalar:
                # list result: aggregate leaf rows into a JSON array
                rel_id = f'r{leaf_rel.ho_id}'
                fk_pk_fields = list(leaf_rel._ho_pkey.keys())
                filter_clause = (
                    f' filter (where {rel_id}."{fk_pk_fields[0]}" is not null)'
                    if fk_pk_fields else ''
                )
                columns.append(
                    f"coalesce(json_agg({obj_expr}){filter_clause}, '[]'::json) as \"{alias}\""
                )
            else:
                # scalar result: at most one leaf row → dict or NULL.
                # When GROUP BY is present wrap in json_agg and extract element 0.
                if has_reverse:
                    rel_id = f'r{leaf_rel.ho_id}'
                    fk_pk_fields = list(leaf_rel._ho_pkey.keys())
                    filter_clause = (
                        f' filter (where {rel_id}."{fk_pk_fields[0]}" is not null)'
                        if fk_pk_fields else ''
                    )
                    col_expr = f'(json_agg({obj_expr}){filter_clause})->0'
                else:
                    col_expr = obj_expr
                columns.append(f"{col_expr} as \"{alias}\"")

        group_by = [f'r{self.ho_id}."{pk}"' for pk in self._ho_pkey] if has_reverse else []

        stmt = ASTSelect(
            columns=columns,
            from_table=self._ho_sql_id(),
            only=bool(self._ho_only),
            joins=self._ho_ast_joins,
            where=where_expr,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return stmt.to_sql()

    def ho_unaccent(self, *fields_names):
        "Sets unaccent for each field listed in fields_names"
        for field_name in fields_names:
            if not isinstance(self.__dict__[field_name], Field):
                raise ValueError(f'{field_name} is not a Field!')
            self.__dict__[field_name].unaccent = True
        return self

    def ho_mogrify(self):
        """Print the SQL SELECT that would be executed and return ``self``.

        Activates SQL tracing for the next query on this object. The query
        is printed to stderr when the next executor is called. Useful for
        debugging predicate composition.

        Returns:
            self — for chaining.

        Example:
            ```python
            Author(last_name='Martin').ho_mogrify().ho_count()
            ```
            displays:
            ```sql
            select
            count(*) from (select
            r... .*
            from
            "blog"."author" as r...
            where
                (r... ."name" = 'Martin'::text)) as ho_count
            ```
        """
        self._ho_mogrify = True
        return self

    def _ho_prep_count(self, *args, distinct=False):
        """Prepare a COUNT query. Returns (query, values)."""
        self._ho_query = "select"
        distinct = 'distinct' if distinct else ''
        query, values = self._ho_prep_select(*args, distinct=distinct)
        query = f'select\n  count(*) from ({query}) as ho_count'
        return query, values

    # @utils.trace
    def ho_count(self, *args, distinct:bool=False):
        """Return the number of rows that satisfy the predicate. *Executes SQL.*

        Args:
            *args: column names for the inner SELECT (useful with
                ``distinct=True``).
            distinct (bool): if ``True``, count only distinct tuples.
                Default: ``False``.

        Returns:
            int: the cardinality of the extension.

        Example:
            ho_count usage:
                ```python
                Author().ho_count()                    # total number of authors
                Author(last_name='Martin').ho_count()  # subset cardinality
                ```

        *New in version 0.18.0:* ``distinct`` parameter.
        """
        query, values = self._ho_prep_count(*args, distinct=distinct)
        return self.__execute(query, values).fetchone()['count']

    def ho_is_empty(self):
        """Return ``True`` if the extension is empty, ``False`` otherwise. *Executes SQL.*

        Returns:
            bool

        Example:
            ho_is_empty usage:
                ```python
                Author(last_name='Unknown').ho_is_empty()  # True if no such author
                ```
        """
        return self.ho_count() == 0

    # --- Async variants of executor methods ---

    async def ho_ainsert(self, *args) -> dict:
        """Async variant of ho_insert. *Executes SQL.*

        *New in version 0.18.0.*
        """
        query, vals = self._ho_prep_insert(*args)
        cursor = await self.__aexecute(query, vals)
        res = await cursor.fetchall() or [{}]
        return res[0]

    async def ho_aselect(self, *args,
        distinct: bool=False, order_by: str=None, limit: int=None, offset: int=None):
        """Async variant of ho_select. Returns a list of dicts (not a generator). *Executes SQL.*

        *New in version 0.18.0.*
        """
        query, values, can_dedup, pk_names = self._ho_prep_select_query(
            *args, distinct=distinct, order_by=order_by, limit=limit, offset=offset)
        cursor = await self.__aexecute(query, values)
        rows = []
        seen = set()
        for elt in await cursor.fetchall():
            row = elt
            if can_dedup:
                pk_key = tuple(row[pk] for pk in pk_names)
                if pk_key in seen:
                    continue
                seen.add(pk_key)
            rows.append(row)
        return rows

    async def ho_aupdate(self, *args, update_all=False, **kwargs):
        """Async variant of ho_update. *Executes SQL.*

        *New in version 0.18.0.*
        """
        prep = self._ho_prep_update(*args, update_all=update_all, **kwargs)
        if prep is None:
            return None
        query, vals, update_args = prep
        cursor = await self.__aexecute(query, vals)
        for field_name, value in update_args.items():
            self._ho_fields[field_name].set(value)
        if args:
            return await cursor.fetchall()
        return None

    async def ho_adelete(self, *args, delete_all=False):
        """Async variant of ho_delete. *Executes SQL.*

        *New in version 0.18.0.*
        """
        query, vals = self._ho_prep_delete(*args, delete_all=delete_all)
        cursor = await self.__aexecute(query, vals)
        if args:
            return await cursor.fetchall()
        return None

    async def ho_acount(self, *args, distinct: bool=False) -> int:
        """Async variant of ho_count. *Executes SQL.*

        *New in version 0.18.0.*
        """
        query, values = self._ho_prep_count(*args, distinct=distinct)
        cursor = await self.__aexecute(query, values)
        row = await cursor.fetchone()
        return row['count']

    async def ho_ais_empty(self) -> bool:
        """Async variant of ho_is_empty. *Executes SQL.*

        *New in version 0.18.0.*
        """
        return (await self.ho_acount()) == 0

    @classmethod
    async def ho_acopy(cls, data, columns=None) -> int:
        """Async variant of :meth:`ho_copy`. *Executes SQL.*

        Requires an async connection opened with ``await model.aconnect()``.

        *New in version 0.18.12.*
        """
        cls()._ho_check_writable()
        aconn = cls._ho_model._aconnection
        if hasattr(data, 'read'):
            if columns is None:
                header = data.readline().rstrip('\n')
                columns = [c.strip() for c in header.split(',')]
            cols = ', '.join(f'"{c}"' for c in columns)
            stmt = f'copy {cls._qrn} ({cols}) from stdin (format csv)'
            count = 0
            async with aconn.cursor().copy(stmt) as copy:
                for line in data:
                    await copy.write(line)
                    count += 1
            return count
        else:
            if not data:
                raise ValueError('ho_acopy: data must not be empty')
            columns = list(data[0].keys())
            cols = ', '.join(f'"{c}"' for c in columns)
            stmt = f'copy {cls._qrn} ({cols}) from stdin'
            async with aconn.cursor().copy(stmt) as copy:
                for row in data:
                    await copy.write_row([row[c] for c in columns])
            return len(data)

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
        """Cast a relation to a related relation in the PostgreSQL inheritance hierarchy.

        The target ``qrn`` must either be an ancestor or a descendant of this
        relation in the PostgreSQL table-inheritance hierarchy.  The check is
        performed via the Python MRO, which :mod:`half_orm.relation_factory`
        builds to mirror the PostgreSQL hierarchy.

        Args:
            qrn (str): qualified relation name of the target (e.g. ``'blog.event'``).

        Returns:
            Relation: a new instance of the target class carrying the same
            field constraints and join state as ``self``.

        Raises:
            CastError: if ``qrn`` is not related to this relation by inheritance.
        """
        target_class = self._ho_model._import_class(qrn)
        self_ancestors   = {cls._t_fqrn for cls in type(self).__mro__       if hasattr(cls, '_t_fqrn')}
        target_ancestors = {cls._t_fqrn for cls in target_class.__mro__     if hasattr(cls, '_t_fqrn')}
        if target_class._t_fqrn not in self_ancestors and self._t_fqrn not in target_ancestors:
            raise relation_errors.CastError(self, qrn)
        new = target_class(**self.__to_dict_val_comp())
        new._ho_id_cast = id(self)
        new._ho_join_to = self._ho_join_to
        new._ho_set_operators = self._ho_set_operators
        new._ho_neg = self._ho_neg
        new._ho_only = self._ho_only
        new._ho_union_branches = self._ho_union_branches
        new._ho_except_branches = self._ho_except_branches
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
        # If either side carries FK joins (or is itself already a UNION),
        # the standard JOIN+WHERE approach would merge incompatible join
        # structures.  Fall back to a true UNION instead.
        if (self._ho_join_to or right._ho_join_to or
                self._ho_union_branches is not None or
                right._ho_union_branches is not None):
            new = self()   # unconstrained container of the same type
            new._ho_union_branches = (self, right)
            # Keep _ho_set_operators populated so ho_is_set() stays correct.
            new._ho_set_operators.left = self
            new._ho_set_operators.operator = 'or'
            new._ho_set_operators.right = right
            return new
        return self.__set__op__("or", right)

    def __ior__(self, right):
        self = self | right
        return self

    def __sub__(self, right):
        if (self._ho_join_to or right._ho_join_to or
                self._ho_union_branches is not None or
                self._ho_except_branches is not None or
                right._ho_union_branches is not None or
                right._ho_except_branches is not None):
            new = self()   # unconstrained container of the same type
            new._ho_except_branches = (self, right)
            new._ho_set_operators.left = self
            new._ho_set_operators.operator = 'and not'
            new._ho_set_operators.right = right
            return new
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
        query, values = self._ho_prep_select()
        for elt in self.__execute(query, values):
            yield elt

    def __next__(self):
        return next(self.ho_select())

def singleton(fct):
    """Decorator that enforces a singleton predicate before calling the method.

    Calls :meth:`~half_orm.relation.Relation.ho_assert_is_singleton` on
    ``self`` before executing the decorated method. Raises
    :exc:`~half_orm.relation_errors.NotASingletonError` if the predicate
    does not identify exactly one row. No database query is performed.

    Use this on any method that must operate on a single, identified row.

    Example:
        singleton decorator usage:
            ```python
            @register
            class Author(blog.get_relation_class('blog.author')):
                Fkeys = {'post_rfk': '_reverse_fkey_blog_post_author_id'}

                @singleton
                def publish(self, title: str, content: str):
                    return self.post_rfk(title=title, content=content).ho_insert()

            Author(id=1).publish('My post', 'Content here')   # OK
            Author(last_name='Martin').publish('…', '…')      # raises NotASingletonError
            ```

    *Changed in version 0.18.0:* the check is now purely structural (no database query).
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
    """Decorator that wraps a Relation method in a database transaction.

    Every INSERT / UPDATE / DELETE executed inside the decorated method runs
    inside a single atomic unit. Commits on normal return, rolls back and
    re-raises on any exception.

    Nested ``@transaction`` calls use PostgreSQL savepoints: a failure in an
    inner method rolls back only that inner scope.

    Example:
        transaction decorator usage:
            ```python
            from half_orm.relation import transaction

            @register
            class Author(blog.get_relation_class('blog.author')):
                @transaction
                def publish_many(self, posts):
                    for title, content in posts:
                        self.post_rfk(title=title, content=content).ho_insert()
            ```

    """
    @wraps(fct)
    def wrapper(self, *args, **kwargs):
        with Transaction(self._ho_model):
            return fct(self, *args, **kwargs)
    return wrapper
