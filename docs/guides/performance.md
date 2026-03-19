# Performance Optimization

## Async Concurrency

halfORM supports async I/O through psycopg 3's `AsyncConnection`.  Use async
execution when you need to run several independent queries at the same time — for
example fetching data from multiple tables without waiting for each query to finish
before starting the next one.

### Setup

```python
import asyncio
from half_orm.model import Model

db = Model('my_database')
Person = db.get_relation_class('public.person')
Order  = db.get_relation_class('public.order')
```

Open **one** async connection per process (or per request in a web framework) and
close it when done:

```python
async def main():
    await db.aconnect()
    try:
        await run_queries()
    finally:
        await db.adisconnect()

asyncio.run(main())
```

### Fan-out pattern

Run independent queries concurrently with `asyncio.gather`:

```python
async def dashboard_data(user_id: int):
    person  = Person(id=user_id)
    orders  = Order(user_id=user_id)

    profile, recent_orders, order_count = await asyncio.gather(
        person.ho_aselect(),
        orders.ho_order_by('created_at desc').ho_limit(5).ho_aselect(),
        orders.ho_acount(),
    )
    return profile, recent_orders, order_count
```

This sends all three queries to PostgreSQL at the same time and collects the
results as they arrive, instead of executing them sequentially.

### Async executor reference

| Method | Returns | Notes |
|---|---|---|
| `await rel.ho_aselect(*fields)` | `list[dict]` | All matching rows |
| `await rel.ho_acount()` | `int` | Row count |
| `await rel.ho_ais_empty()` | `bool` | True if no rows match |
| `await rel.ho_ainsert()` | `dict` | Inserted row |
| `await rel.ho_aupdate(**kwargs)` | — | Updates matching rows |
| `await rel.ho_adelete()` | — | Deletes matching rows |

!!! note "ho_aselect returns a list"
    Unlike `ho_select()` which returns a generator, `ho_aselect()` returns a
    plain `list` so the underlying cursor can be closed before yielding control
    back to the event loop.

### When async helps

- **Web APIs**: fetch data for a response from multiple tables concurrently.
- **Batch processing**: run independent per-record queries in parallel.
- **Dashboards**: aggregate several counts/sums in one `gather` call.

### When async does NOT help

- A single sequential operation (one query, one insert) — sync is simpler.
- Queries that depend on each other's results — `await` them sequentially.
- CPU-bound work — use `multiprocessing` instead.

## Query Limiting

Always constrain large result sets to avoid fetching more rows than needed:

```python
# Limit result size
recent = Person().ho_order_by('created_at desc').ho_limit(100).ho_select()

# Check before fetching
if not Person(email='user@example.com').ho_is_empty():
    person = Person(email='user@example.com').ho_get()
```

## Count vs. Select

Prefer `ho_count()` / `ho_acount()` over fetching rows just to count them:

```python
# Fast: single COUNT(*) query
n = Order(status='pending').ho_count()

# Slow: fetch all rows just to count
n = len(list(Order(status='pending').ho_select()))
```
