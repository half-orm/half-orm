# Relation

A `Relation` object is a **predicate** — it describes the logical condition
that rows must satisfy to belong to the relation. Its *extension* is the set
of rows currently satisfying that predicate in the database.

Instantiating with keyword arguments specialises the predicate. No SQL is
executed until you call an executor method.

```python
Author()                          # tautology — the whole table
Author(last_name='Martin')        # subset: "is an author named Martin"
Author(last_name='Martin', id=42) # at most one row
```

See [Learn halfORM in half an hour](../half-an-hour.md) for a full walkthrough.

---

## Executors

These methods execute SQL and return results immediately.

::: half_orm.relation.Relation.ho_insert
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_select
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_count
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_is_empty
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_update
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_delete
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_assert_is_singleton
    options:
      show_root_heading: true
      show_source: false

---

## Async executors

Async counterparts of every executor. Require an async connection opened
with `await model.aconnect()`. Return plain values (not generators) so the
cursor can be closed before returning to the caller.

::: half_orm.relation.Relation.ho_ainsert
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_aselect
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_acount
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_ais_empty
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_aupdate
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_adelete
    options:
      show_root_heading: true
      show_source: false

---

## Introspection

::: half_orm.relation.Relation.ho_is_set
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_where_display
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_mogrify
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_dict
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.Relation.ho_description
    options:
      show_root_heading: true
      show_source: false

---

## Decorators

::: half_orm.relation.singleton
    options:
      show_root_heading: true
      show_source: false

::: half_orm.relation.transaction
    options:
      show_root_heading: true
      show_source: false