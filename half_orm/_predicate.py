#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Canonicalisation of the predicate structure returned by
:meth:`~half_orm.relation.Relation.ho_where_display`.

Kept in a dependency-free leaf module so that both
:mod:`half_orm.relation` and :mod:`half_orm.testing` can use it without
either importing the other, and so that importing the testing helpers
does not pull in the database driver.
"""

__all__ = ['canonical_predicate']


def canonical_predicate(node):
    """Return a hashable, alias-free, canonical form of a predicate node.

    The form produced is a nested tuple, so it can be used as a dictionary
    key or a set member. Relation aliases (``r{ho_id}``), which differ
    between instances of the same query, are dropped, and the operands of
    the commutative operators (``or``, ``and``) are ordered, so that
    ``A | B`` and ``B | A`` canonicalise identically. ``and not`` is not
    commutative and keeps its operand order.

    Args:
        node (dict | None): a node as returned by
            :meth:`~half_orm.relation.Relation.ho_where_display`.

    Returns:
        tuple | None: the canonical form, or ``None`` for an unconstrained
        predicate. Note that ``None`` says nothing about *which* relation
        is unconstrained; callers needing to tell two unconstrained
        relations apart must tag the result with the relation itself, as
        :meth:`~half_orm.relation.Relation.ho_structural_key` does.
    """
    if node is None:
        return None
    op = node.get('operator')
    if op == 'neg':
        return ('neg', canonical_predicate(node['operand']))
    if op:
        left = canonical_predicate(node['left'])
        right = canonical_predicate(node.get('right'))
        if op in ('or', 'and'):
            return (op, *sorted([left, right], key=repr))
        return (op, left, right)   # 'and not' is not commutative
    tables = frozenset(node.get('tables', set()))
    constraints = tuple(sorted(
        (c['relation'][0], c['field'], c['comp'], str(c['value']))
        for c in node.get('constraints', [])
    ))
    leaf = (tables, constraints)
    # A negated compound arrives as a 'neg' node; a negated leaf carries the
    # flag instead. Both canonicalise to the same shape.
    return ('neg', leaf) if node.get('neg') else leaf
