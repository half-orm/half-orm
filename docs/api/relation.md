# Relation

A `Relation` object is a **predicate** — it describes the logical condition
that rows must satisfy to belong to the relation. Its *extension* is the set
of rows currently satisfying that predicate in the database.

Instantiating with keyword arguments specialises the predicate. **No SQL is
executed** until you call an executor method.

```python
Author()                          # tautology — the whole table
Author(last_name='Martin')        # subset: "is an author named Martin"
Author(last_name='Martin', id=42) # at most one row
```

**Executors** (`ho_select`, `ho_insert`, `ho_update`, `ho_delete`, `ho_count`,
`ho_is_empty`) execute SQL immediately and return results.
**Introspection** methods (`ho_assert_is_singleton`, `ho_is_set`,
`ho_where_display`, `ho_mogrify`) inspect or assert on the predicate without
touching the database.

See [Learn halfORM in half an hour](../half-an-hour.md) for a full walkthrough.

---

## Executors

These methods execute SQL immediately and return results.

::: half_orm.relation.Relation.ho_insert
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_select
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_count
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_is_empty
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_update
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_delete
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Async executors

Async counterparts of every executor. Require an async connection opened
with `await model.aconnect()`. Return plain values (not generators) so the
cursor can be closed before returning to the caller.

::: half_orm.relation.Relation.ho_ainsert
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_aselect
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_acount
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_ais_empty
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_aupdate
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_adelete
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Introspection

These methods inspect or assert on the predicate **without executing SQL**.

::: half_orm.relation.Relation.ho_assert_is_singleton
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_is_set
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

!!! warning "Syntactic check, not semantic — risk of data loss"
    `ho_is_set()` inspects the predicate structure only. It returns `True`
    for any predicate built with set operators or FK joins, even when the
    extension is semantically equivalent to the full table:

    ```python
    Post() & Post()                             # True — but = all posts
    Post() | Post(title='a')                    # True — but = all posts
    Post(title='a') | Post(title=('!=', 'a'))   # True — but = all posts
    ```

    Because `ho_delete()` and `ho_update()` allow execution without
    `delete_all=True` / `update_all=True` when `ho_is_set()` is `True`,
    these predicates will silently operate on the **entire table**.

    ```python
    # Deletes ALL posts — no error raised
    (Post() | Post(title='a')).ho_delete()
    ```

    Always verify the actual extension with `ho_count()` or `ho_mogrify()`
    before destructive operations on set-operator predicates.

::: half_orm.relation.Relation.ho_where_display
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_mogrify
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_dict
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_description
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Decorators

::: half_orm.relation.singleton
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.transaction
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

See also: [Transaction](transaction.md) — the context manager equivalent.