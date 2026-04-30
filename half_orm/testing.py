#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Testing utilities for halfORM-based applications.

These helpers work with the dict returned by
:meth:`~half_orm.relation.Relation.ho_where_display` to let you write
**predicate-level tests** — asserting on the structure and values of a
query predicate without executing SQL or inserting test data.

Example::

    from half_orm.testing import leaf_constraints, find_constraints

    result = Post(author_id=1).reviewers().ho_where_display()

    # check that the predicate reaches the author table
    assert any(c['relation'][0] == 'blog.author'
               for c in leaf_constraints(result))

    # check the review-type filter is present
    assert find_constraints(result, field='comment_type', value='review')
"""


def leaf_constraints(node):
    """Return all constraints from a :meth:`ho_where_display` tree.

    Since ``ho_where_display`` pre-aggregates constraints at every level,
    this is a direct read of ``node['constraints']`` — no tree traversal needed.

    Args:
        node (dict | None): the value returned by ``ho_where_display()``.

    Returns:
        list[dict]: flat list of constraint dicts, each with keys
        ``relation``, ``field``, ``comp``, ``value``.
    """
    if node is None:
        return []
    return list(node.get('constraints', []))


def constraint_values(node):
    """Return the list of all constraint values in the predicate tree.

    Args:
        node (dict | None): the value returned by ``ho_where_display()``.

    Returns:
        list: all ``value`` entries across every leaf constraint.
    """
    return [c['value'] for c in leaf_constraints(node)]


def constraint_tables(node):
    """Return the set of all ``schema.table`` names present in the predicate tree.

    Args:
        node (dict | None): the value returned by ``ho_where_display()``.

    Returns:
        set[str]: e.g. ``{'blog.post', 'blog.author'}``.
    """
    return {c['relation'][0] for c in leaf_constraints(node)}


def traversed_tables(node):
    """Return the set of *all* ``schema.table`` names reached by the predicate,
    including tables that are only traversed via JOIN without any field constraint.

    Since ``ho_where_display`` pre-aggregates tables at every level,
    this is a direct read of ``node['tables']`` — no tree traversal needed.

    For tables with at least one constraint, use :func:`constraint_tables` instead.

    Args:
        node (dict | None): the value returned by ``ho_where_display()``.

    Returns:
        set[str]: e.g. ``{'blog.post', 'blog.comment', 'actor.person'}``.
    """
    if node is None:
        return set()
    return set(node.get('tables', set()))


def constraint_fields(node):
    """Return the set of all field names constrained in the predicate tree.

    Args:
        node (dict | None): the value returned by ``ho_where_display()``.

    Returns:
        set[str]: e.g. ``{'id', 'comment_type'}``.
    """
    return {c['field'] for c in leaf_constraints(node)}


def find_constraints(node, *, table=None, field=None, comp=None, value=None):
    """Return constraints matching all provided criteria.

    All keyword arguments are optional; only the provided ones are used
    as filters (AND logic).

    Args:
        node (dict | None): the value returned by ``ho_where_display()``.
        table (str | None): ``'schema.table'`` to filter on.
        field (str | None): column name to filter on.
        comp  (str | None): comparator (``'='``, ``'>'``, ``'like'``, …).
        value: Python value to filter on.

    Returns:
        list[dict]: matching constraint dicts.

    Example::

        find_constraints(result, table='blog.comment_type', value='review')
    """
    results = leaf_constraints(node)
    if table is not None:
        results = [c for c in results if c['relation'][0] == table]
    if field is not None:
        results = [c for c in results if c['field'] == field]
    if comp is not None:
        results = [c for c in results if c['comp'] == comp]
    if value is not None:
        results = [c for c in results if c['value'] == value]
    return results


def is_unconstrained(relation):
    """Return ``True`` if *relation* has no constraint at all.

    Equivalent to ``relation.ho_where_display() is None``, but names the
    intent explicitly.

    Args:
        relation: a halfORM relation object.

    Returns:
        bool: ``True`` when the relation is fully unconstrained.

    Example::

        from half_orm.testing import is_unconstrained

        assert is_unconstrained(Person())          # no fields set
        assert not is_unconstrained(Person(id=1))
    """
    return relation.ho_where_display() is None


def assertInvolvesTables(relation, *tables, msg=None):
    """Return ``True`` if *all* given tables appear in the predicate tree,
    or raise :class:`AssertionError` with a diagnostic if any are missing.

    Includes tables that are only traversed via JOIN with no field constraint
    set on them, not just tables that carry a constraint.  To check only
    tables with constraints, use :func:`constraint_tables` directly.

    Args:
        relation: a halfORM relation object.
        *tables (str): one or more ``'schema.table'`` strings that must all
            be present.
        msg (str | None): custom message, overrides the generated diagnostic.

    Returns:
        bool: ``True`` when every table in *tables* is reached.

    Raises:
        AssertionError: with a list of missing tables and found tables when
            at least one expected table is absent.

    Example::

        from half_orm.testing import assertInvolvesTables

        assertInvolvesTables(
            Post(title='Hello').commenters(),
            'blog.post', 'blog.comment', 'actor.person',
        )
    """
    found = traversed_tables(relation.ho_where_display())
    missing = set(tables) - found
    if missing:
        raise AssertionError(
            msg or (
                f"missing tables: {sorted(missing)}\n"
                f"Found: {sorted(found)}"
            )
        )
    return True


def constraint_count(relation, *, table=None, field=None, comp=None, value=None):
    """Return the number of constraints in *relation*'s predicate that match
    all provided criteria.

    All keyword arguments are optional; only the provided ones are used as
    filters (AND logic).  With no criteria, returns the total number of leaf
    constraints.

    Args:
        relation: a halfORM relation object.
        table (str | None): ``'schema.table'`` to filter on.
        field (str | None): column name to filter on.
        comp  (str | None): comparator (``'='``, ``'>'``, ``'like'``, …).
        value: Python value to filter on.

    Returns:
        int: number of matching constraints.

    Example::

        from half_orm.testing import constraint_count

        # exactly one constraint on actor.person
        assert constraint_count(Person(last_name='Martin').posts(),
                                table='actor.person') == 1
    """
    return len(find_constraints(
        relation.ho_where_display(),
        table=table, field=field, comp=comp, value=value,
    ))


def assertConstraintsMatch(relation, *, table=None, field=None, comp='=', value=None, msg=None):
    """Assert that at least one constraint in *relation*'s predicate matches
    all provided criteria.

    Raises :class:`AssertionError` with a diagnostic listing every leaf
    constraint that was actually found when no match exists — much more useful
    than the bare ``AssertionError: False`` produced by
    ``assertTrue(constraints_match(...))``.

    Args:
        relation: a halfORM relation object.
        table (str | None): ``'schema.table'`` to match.
        field (str | None): column name to match.
        comp  (str | None): comparator (``'='``, ``'>'``, ``'like'``, …).
        value: Python value to match.
        msg   (str | None): custom message, overrides the generated one.

    Raises:
        AssertionError: when no constraint satisfies all criteria.

    Example::

        from half_orm.testing import assertConstraintsMatch

        assertConstraintsMatch(
            Person(last_name='Martin').posts(),
            table='actor.person', field='last_name', value='Martin',
        )
    """
    node = relation.ho_where_display()
    matched = find_constraints(node, table=table, field=field, comp=comp, value=value)
    if not matched:
        criteria = {k: v for k, v in [
            ('table', table), ('field', field), ('comp', comp), ('value', value),
        ] if v is not None}
        found = leaf_constraints(node)
        raise AssertionError(
            msg or f"no constraint matched {criteria}\nFound: {found}"
        )


def _canonical(node):
    """Return a normalised, alias-free representation of a ho_where_display node.

    Used by :func:`assertSamePredicate` to compare predicates structurally,
    ignoring relation aliases (``r{ho_id}``) and the left/right ordering of
    commutative operators (``or``, ``and``).
    """
    if node is None:
        return None
    op = node.get('operator')
    if op == 'neg':
        return ('neg', _canonical(node['operand']))
    if op:
        left  = _canonical(node['left'])
        right = _canonical(node.get('right'))
        if op in ('or', 'and'):
            return (op, *sorted([left, right], key=repr))
        return (op, left, right)   # 'and not' is not commutative
    tables = frozenset(node.get('tables', set()))
    constraints = tuple(sorted(
        (c['relation'][0], c['field'], c['comp'], str(c['value']))
        for c in node.get('constraints', [])
    ))
    return (tables, constraints)


def assertSamePredicate(rel1, rel2, msg=None):
    """Assert that two relations produce the same logical predicate.

    Compares predicates structurally, ignoring relation aliases (``r{ho_id}``)
    which differ between object instances even for equivalent queries.
    Commutative operators (``or``, ``and``) are normalised so that
    ``A | B`` and ``B | A`` are considered equal; ``and not`` is not
    commutative and is compared as-is.

    Args:
        rel1: first halfORM relation object.
        rel2: second halfORM relation object.
        msg (str | None): custom message, overrides the generated diagnostic.

    Raises:
        AssertionError: when the two predicates differ structurally.

    Example::

        from half_orm.testing import assertSamePredicate

        assertSamePredicate(
            post.reviewers(),
            post.rfk_comments().author_fk(),
        )
    """
    c1 = _canonical(rel1.ho_where_display())
    c2 = _canonical(rel2.ho_where_display())
    if c1 != c2:
        raise AssertionError(
            msg or f"predicates differ:\n  left:  {c1}\n  right: {c2}"
        )


def constraints_match(relation, *, table=None, field=None, comp='=', value=None):
    """Return ``True`` if at least one constraint in *relation*'s predicate
    matches all provided criteria.

    Takes a :class:`~half_orm.relation.Relation` object directly — calls
    :meth:`~half_orm.relation.Relation.ho_where_display` internally.

    Args:
        relation: a halfORM relation object.
        table (str | None): ``'schema.table'`` to match.
        field (str | None): column name to match.
        comp  (str | None): comparator (``'='``, ``'>'``, ``'like'``, …).
        value: Python value to match.

    Returns:
        bool: ``True`` if at least one constraint satisfies all criteria.

    Example::

        from half_orm.testing import constraints_match

        posts = Person(last_name='Martin').posts()
        assert constraints_match(posts, table='actor.person',
                                 field='last_name', comp='=', value='Martin')
    """
    return bool(find_constraints(
        relation.ho_where_display(),
        table=table, field=field, comp=comp, value=value,
    ))