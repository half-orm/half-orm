# Testing utilities

`half_orm.testing` provides helpers for writing **predicate-level tests** —
assertions on the structure and values of a query predicate without executing
SQL or inserting test data.

The helpers work with the dict returned by
[`Relation.ho_where_display()`](relation.md), which exposes the JOIN/WHERE
tree built by your business methods.

---

## Why predicate-level tests?

Business methods that traverse foreign keys (e.g. `Person.posts()`,
`Post.commenters()`) build a predicate over multiple tables.
You can verify that predicate without hitting the database:

```python
from half_orm.testing import assertConstraintsMatch
from myapp.actor.person import Person

def test_posts_carries_last_name():
    assertConstraintsMatch(
        Person(last_name='Martin').posts(),
        table='actor.person', field='last_name', value='Martin',
    )

def test_commenters_traverses_full_path():
    assertInvolvesTables(
        Post(title='Hello').commenters(),
        'blog.post', 'blog.comment', 'actor.person',
    )
```

Tests pass or fail based on the *structure* of the query, making them
fast, deterministic, and database-free.

---

## Assertion helpers

These functions raise :class:`AssertionError` with a diagnostic message on
failure, following the `assert*` convention of :class:`unittest.TestCase`.

::: half_orm.testing.assertConstraintsMatch
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.testing.assertInvolvesTables
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.testing.assertSamePredicate
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Query helpers

These functions return data for use in custom assertions or for building
more complex checks.

::: half_orm.testing.constraints_match
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.testing.find_constraints
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.testing.constraint_count
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.testing.is_unconstrained
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.testing.traversed_tables
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.testing.constraint_tables
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.testing.leaf_constraints
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.testing.constraint_fields
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.testing.constraint_values
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3