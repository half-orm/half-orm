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

## Reference

::: half_orm.relation
    options:
      show_source: true
      show_root_heading: true
