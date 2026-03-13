# -*- coding: utf-8 -*-

"""SQL Abstract Syntax Tree for half_orm query construction.

This module provides lightweight dataclasses that represent the *structure*
of an SQL query independently of its textual rendering.  Each node exposes
a ``to_sql()`` method that returns ``(query_string, values_list)`` ready
for psycopg2 execution.

Typical usage (phase 2+) — replace string-concatenation in Relation with::

    node = Select(columns=[...], from_clause=..., where=..., ...)
    sql, vals = node.to_sql()

The hierarchy mirrors what ``relation.py`` already builds implicitly:

* **Expressions (WHERE)** — ``Expr`` and subclasses
* **Clauses** — ``Join``, ``Returning``
* **Statements** — ``Select``, ``Insert``, ``Update``, ``Delete``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# WHERE expression tree
# ---------------------------------------------------------------------------

class Expr:
    """Base class for all WHERE-clause expression nodes."""

    def to_sql(self) -> Tuple[str, list]:
        """Return ``(sql_fragment, values)`` for this expression."""
        raise NotImplementedError


@dataclass
class FieldExpr(Expr):
    """A single field condition, e.g. ``r42."name" = %s::text``.

    Parameters
    ----------
    column : str
        Fully qualified column reference (e.g. ``r42."name"``).
    comp : str
        SQL comparison operator (``=``, ``like``, ``is``, ``in``, …).
    placeholder : str
        The ``%s`` placeholder with optional cast (e.g. ``%s::text``).
    value : object
        The Python value to bind.
    unaccent : bool
        Wrap both sides in ``unaccent()``.
    array_any : bool
        Use ``%s = ANY(column)`` form for array columns.
    """
    column: str
    comp: str
    placeholder: str
    value: object
    unaccent: bool = False
    array_any: bool = False

    def to_sql(self) -> Tuple[str, list]:
        if self.array_any:
            return f"{self.placeholder} = ANY({self.column})", [self.value]
        if self.unaccent:
            return (
                f"unaccent({self.column}) {self.comp} unaccent({self.placeholder})",
                [self.value],
            )
        return f"{self.column} {self.comp} {self.placeholder}", [self.value]


@dataclass
class And(Expr):
    """Conjunction of child expressions."""
    children: List[Expr]

    def to_sql(self) -> Tuple[str, list]:
        if not self.children:
            return "", []
        parts, vals = [], []
        for child in self.children:
            sql, v = child.to_sql()
            parts.append(sql)
            vals.extend(v)
        return "  and ".join(parts), vals


@dataclass
class Or(Expr):
    """Disjunction of child expressions."""
    children: List[Expr]

    def to_sql(self) -> Tuple[str, list]:
        if not self.children:
            return "", []
        parts, vals = [], []
        for child in self.children:
            sql, v = child.to_sql()
            parts.append(sql)
            vals.extend(v)
        return " or\n    ".join(parts), vals


@dataclass
class Not(Expr):
    """Negation wrapper."""
    child: Expr

    def to_sql(self) -> Tuple[str, list]:
        sql, vals = self.child.to_sql()
        return f"not ({sql})", vals


@dataclass
class Raw(Expr):
    """A raw SQL fragment with optional values (escape hatch).

    Useful for literal constants like ``TRUE``, ``FALSE``, or sub-selects
    that have no dedicated node yet.
    """
    sql: str
    values: list = field(default_factory=list)

    def to_sql(self) -> Tuple[str, list]:
        return self.sql, list(self.values)


@dataclass
class Group(Expr):
    """Wraps an expression in parentheses: ``(child)``."""
    child: Expr

    def to_sql(self) -> Tuple[str, list]:
        sql, vals = self.child.to_sql()
        return f"({sql})", vals


@dataclass
class SetOp(Expr):
    """A binary set-algebra operation (``and`` / ``or`` / ``and not``).

    This maps directly to the existing ``_SetOperators`` tree walk
    performed by ``__walk_op``.
    """
    left: Expr
    operator: str          # "and", "or", "and not"
    right: Optional[Expr]  # None only when operator is implicit negation

    def to_sql(self) -> Tuple[str, list]:
        l_sql, l_vals = self.left.to_sql()
        if self.right is None:
            return l_sql, l_vals
        r_sql, r_vals = self.right.to_sql()
        return f"{l_sql} {self.operator}\n    {r_sql}", l_vals + r_vals


# ---------------------------------------------------------------------------
# JOIN clause
# ---------------------------------------------------------------------------

@dataclass
class Join:
    """A single JOIN clause.

    Parameters
    ----------
    table : str
        The joined table with its alias, e.g. ``"schema"."table" as r42``.
    on : str
        The ON condition, e.g. ``(r42."id" = r1."person_id")``.
    where : Expr | None
        Additional WHERE conditions contributed by the joined relation.
    """
    table: str
    on: str
    where: Optional[Expr] = None

    def to_sql(self) -> Tuple[str, list]:
        sql = f"\n  join {self.table} on\n   {self.on}"
        vals: list = []
        if self.where is not None:
            w_sql, w_vals = self.where.to_sql()
            if w_sql:
                sql += f" and\n {w_sql}"
                vals = w_vals
        return sql, vals


# ---------------------------------------------------------------------------
# RETURNING clause
# ---------------------------------------------------------------------------

@dataclass
class Returning:
    """SQL RETURNING clause."""
    columns: List[str]

    def to_sql(self) -> str:
        return f" returning {', '.join(self.columns)}"


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------

@dataclass
class Select:
    """A complete SELECT statement.

    Parameters
    ----------
    columns : list[str]
        Column expressions to select (e.g. ``["r42.*"]``).
    from_table : str
        The primary table with alias (e.g. ``"schema"."table" as r42``).
    only : bool
        Emit ``ONLY`` before the table name.
    joins : list[Join]
        JOIN clauses in order.
    where : Expr | None
        Top-level WHERE expression.
    distinct : bool
        Emit ``DISTINCT``.
    order_by : str | None
        Raw ORDER BY string.
    limit : int | None
    offset : int | None
    """
    columns: List[str]
    from_table: str
    only: bool = False
    joins: List[Join] = field(default_factory=list)
    where: Optional[Expr] = None
    distinct: bool = False
    order_by: Optional[str] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    def to_sql(self) -> Tuple[str, list]:
        vals: list = []

        # SELECT [DISTINCT] columns
        dist = "distinct " if self.distinct else ""
        cols = ", ".join(self.columns)
        sql = f"select\n {dist}{cols}"

        # FROM [ONLY] table
        only = "only " if self.only else ""
        sql += f"\nfrom\n  {only}{self.from_table}"

        # JOINs  (values from joins come *before* WHERE values,
        # matching the current _ho_sql_values + values ordering)
        join_parts: list[str] = []
        for j in self.joins:
            j_sql, j_vals = j.to_sql()
            join_parts.append(j_sql)
            vals.extend(j_vals)
        if join_parts:
            sql += "".join(join_parts)

        # WHERE
        if self.where is not None:
            w_sql, w_vals = self.where.to_sql()
            if w_sql:
                sql += f"\nwhere\n    {w_sql}"
                vals.extend(w_vals)

        # Trailing clauses
        if self.order_by:
            sql += f" order by {self.order_by}"
        if self.limit is not None:
            sql += f" limit {self.limit}"
        if self.offset is not None:
            sql += f" offset {self.offset}"

        return sql, vals


@dataclass
class Insert:
    """A complete INSERT statement.

    Parameters
    ----------
    table : str
        Fully qualified table name (no alias).
    columns : list[str]
        Column names to insert into.
    placeholders : list[str]
        One ``%s`` per column (may include sub-selects for FK values).
    values : list
        Bound values matching the placeholders.
    returning : Returning | None
    """
    table: str
    columns: List[str]
    placeholders: List[str]
    values: list
    returning: Optional[Returning] = None

    def to_sql(self) -> Tuple[str, list]:
        cols = ", ".join(self.columns)
        phs = ", ".join(self.placeholders)
        sql = f"insert into {self.table} ({cols}) values ({phs})"
        if self.returning:
            sql += self.returning.to_sql()
        return sql, list(self.values)


@dataclass
class Update:
    """A complete UPDATE statement.

    Parameters
    ----------
    table : str
        Fully qualified table name (no alias).
    set_clause : list[tuple[str, object]]
        ``[('"col" = %s', value), ...]`` pairs.
    where : Expr | None
    fk_where : str | None
        Extra WHERE fragment from foreign-key constraints.
    fk_values : list
        Values for the fk_where fragment.
    returning : Returning | None
    """
    table: str
    set_clause: List[Tuple[str, object]]
    where: Optional[Expr] = None
    fk_where: Optional[str] = None
    fk_values: list = field(default_factory=list)
    returning: Optional[Returning] = None

    def to_sql(self) -> Tuple[str, list]:
        # SET
        set_parts = [col for col, _ in self.set_clause]
        set_vals = [val for _, val in self.set_clause]
        sql = f"update {self.table} set {', '.join(set_parts)}"

        vals: list = list(set_vals)

        # WHERE
        where_parts: list[str] = []
        if self.where is not None:
            w_sql, w_vals = self.where.to_sql()
            if w_sql:
                where_parts.append(w_sql)
                vals.extend(w_vals)
        if self.fk_where:
            where_parts.append(self.fk_where)
            vals.extend(self.fk_values)
        if where_parts:
            sql += f" where {' and '.join(where_parts)}"

        if self.returning:
            sql += self.returning.to_sql()

        return sql, vals


@dataclass
class Delete:
    """A complete DELETE statement.

    Parameters
    ----------
    table : str
        Fully qualified table name (no alias).
    where : Expr | None
    fk_where : str | None
    fk_values : list
    returning : Returning | None
    """
    table: str
    where: Optional[Expr] = None
    fk_where: Optional[str] = None
    fk_values: list = field(default_factory=list)
    returning: Optional[Returning] = None

    def to_sql(self) -> Tuple[str, list]:
        sql = f"delete from {self.table}"
        vals: list = []

        where_parts: list[str] = []
        if self.where is not None:
            w_sql, w_vals = self.where.to_sql()
            if w_sql:
                where_parts.append(w_sql)
                vals.extend(w_vals)
        if self.fk_where:
            where_parts.append(self.fk_where)
            vals.extend(self.fk_values)
        if where_parts:
            sql += f" where {' and '.join(where_parts)}"

        if self.returning:
            sql += self.returning.to_sql()

        return sql, vals
