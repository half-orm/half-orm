# Transaction

`Transaction` is a context manager that wraps one or more SQL operations
in a single atomic unit: commits on success, rolls back on exception.

Nested `with Transaction(model)` blocks use PostgreSQL savepoints
automatically — an exception in an inner block rolls back only that scope,
leaving the outer transaction intact.

See [Learn halfORM in half an hour](../half-an-hour.md#10-transactions-5-min)
for a full walkthrough.

---

::: half_orm.transaction.Transaction
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3
      members: false