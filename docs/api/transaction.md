# Transaction

`Transaction` is a context manager that wraps one or more SQL operations
in a single atomic unit: commits on success, rolls back on exception.

Nested `with Transaction(model)` blocks use PostgreSQL savepoints
automatically — an exception in an inner block rolls back only that scope,
leaving the outer transaction intact.

See [Learn halfORM in half an hour](../half-an-hour.md#10-transactions-5-min)
for a full walkthrough.

## Work that must wait for the COMMIT

A mutation only becomes a fact when the transaction commits. Anything whose
effect leaves the database — a notification, a cache eviction, a websocket
event — must therefore be deferred until then, or it announces rows that a
rollback has taken back.

```python
with Transaction(blog):
    post = Post(title='First post').ho_insert()
    Transaction(blog).after_commit(lambda: broadcast('post', 'create', post['id']))
    index(post)          # raises → nothing is broadcast
# the COMMIT having succeeded, the callback runs here
```

`Transaction(model).after_commit(...)` reaches the open transaction of the
current thread from anywhere in the call stack: a model method can register a
callback without knowing who opened the transaction, and without a reference
to the object that did. Outside a transaction the callback runs immediately,
a mutation committing on its own.

`AsyncTransaction` carries the same two methods as coroutines — `await
AsyncTransaction(model).after_commit(cb)` — accepting coroutine functions and
plain ones alike.

---

::: half_orm.transaction.Transaction
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3
      members:
        - after_commit
        - after_rollback