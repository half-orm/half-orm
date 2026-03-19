# Relation

<!-- TODO: Module overview -->
<!-- TODO: Key concepts -->
<!-- TODO: Usage patterns -->

!!! note "API Status"
    API documentation is auto-generated from docstrings. Ensure docstrings are comprehensive.

## Overview

## Method Categories

Relation methods are divided into two categories:

### Query Builders (Lazy)
Return modified relation objects without executing SQL:
- `ho_order_by()`, `ho_limit()`, `ho_offset()`
- Set operations: `&`, `|`, `-`, `^`
- Foreign key navigation: `relation_fk()`, `relation_rfk()`

### Query Executors (Eager)
Execute SQL immediately and return results:
- `ho_select(*fields)` → **Generator**
- `ho_count()` → **int**
- `ho_is_empty()` → **bool**
- `ho_insert()`, `ho_update()`, `ho_delete()` → **dict**

!!! warning "ho_get() is deprecated"
    Use the `@singleton` decorator instead. See [The Singleton Pattern](../fundamentals.md#the-singleton-pattern).

!!! warning "No Chaining After Execution"
    ```python
    # ✅ Chain builders first
    query = Author().ho_order_by('name').ho_limit(10)
    
    # ✅ Then execute
    results = query.ho_select('name')  # Returns generator
    
    # ❌ Cannot chain after execution
    # results.ho_order_by('email')  # ERROR!
    ```

!!! tip "Conceptual Background"
    This builder/executor pattern is core to halfORM's design. Learn more in [halfORM Fundamentals](../fundamentals.md#method-categories-builders-vs-executors).

### Async Executors (Eager, coroutines)
Async counterparts of every query executor. Require an async connection opened via
`await model.aconnect()` before use, and closed with `await model.adisconnect()`.
Return plain values (not generators) so the underlying cursor can be closed immediately.

- `ho_aselect(*fields)` → **list[dict]**
- `ho_acount()` → **int**
- `ho_ais_empty()` → **bool**
- `ho_ainsert()` → **dict**
- `ho_aupdate(**kwargs)` → —
- `ho_adelete()` → —

!!! example "Concurrent queries with asyncio.gather"
    ```python
    import asyncio
    from half_orm.model import Model

    db = Model('my_database')
    Person = db.get_relation_class('public.person')

    async def main():
        await db.aconnect()
        try:
            admins, users = await asyncio.gather(
                Person(role='admin').ho_aselect(),
                Person(role='user').ho_aselect(),
            )
        finally:
            await db.adisconnect()

    asyncio.run(main())
    ```

### Introspection (no SQL)
Inspect the query intent without executing anything:
- `ho_where_display()` → **dict | None** — returns the JOIN/WHERE clauses as built on the object
- `ho_is_set()` → **bool** — True if at least one field or FK constraint is set

## Reference

::: half_orm.relation
    options:
      show_source: true
      show_root_heading: true
