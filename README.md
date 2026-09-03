# halfORM

[![PyPI version](https://img.shields.io/pypi/v/half_orm)](https://pypi.org/project/half-orm/)
[![Python versions](https://img.shields.io/badge/Python-%20≥%203.9-blue)](https://www.python.org)
[![PostgreSQL versions](https://img.shields.io/badge/PostgreSQL-%20≥%209.6-blue)](https://www.postgresql.org)
[![License](https://img.shields.io/pypi/l/half_orm?color=green)](https://pypi.org/project/half-orm/)
[![Tests](https://github.com/half-orm/half-orm/actions/workflows/python-package.yml/badge.svg)](https://github.com/half-orm/half-orm/actions/workflows/python-package.yml)
[![Coverage](https://coveralls.io/repos/github/half-orm/half-orm/badge.svg?branch=main)](https://coveralls.io/github/half-orm/half-orm?branch=main)
[![Downloads](https://static.pepy.tech/badge/half_orm)](https://pepy.tech/project/half_orm)

> ## ⚠️ BREAKING CHANGES in v1.0.0
>
> **Legacy unprefixed API removed** — the pre-`ho_` method names, deprecated
> since 0.x, no longer exist: `select`, `insert`, `update`, `delete`, `get`,
> `count`, `is_empty`, `unaccent`, `order_by`, `limit`, `offset`, `_mogrify`.
> Use their `ho_`-prefixed equivalents (`ho_select`, `ho_insert`, `ho_update`,
> `ho_delete`, `ho_get`, `ho_count`, `ho_is_empty`, `ho_unaccent`, `ho_mogrify`,
> passing `order_by`/`limit`/`offset` as `ho_select()` keyword arguments).
>
> **`DC_Relation`** removed from `half_orm.relation` — this IDE type-checking
> stub is now generated per-project by `half-orm-dev` instead of shipped in
> the library.
>
> **`ho_get()`** is now public and returns a `dict` directly. It raises
> `NotFoundError` (0 rows) or `MultipleRowsError` (> 1 row) instead of
> counting first.
>
> **Deprecated query-builder setters removed** — `ho_limit`, `ho_offset`,
> `ho_order_by`, `ho_distinct` no longer exist as setters. Pass these as
> keyword arguments to `ho_select()`:
> ```python
> # Before (0.x)
> rel.ho_limit = 10
> rel.ho_order_by = 'name'
> list(rel)
>
> # After (1.0)
> list(rel.ho_select(limit=10, order_by='name'))
> ```
>
> **`FKEYS_PROPERTIES` / `FKEYS`** class attributes removed — use `Fkeys` only.
>
> **`ho_cast()`** now raises `CastError` if the target is not in the
> PostgreSQL inheritance hierarchy of the relation.
>
> See [CHANGELOG.md](CHANGELOG.md) for the full list of changes.

halfORM is a database-first ORM for PostgreSQL. Your schema lives in the
database; halfORM introspects it at runtime and gives you Python objects to work
with your data. No migrations, no code generation.

**The central idea:** a `Relation` object is a **predicate**. It describes the
logical condition that rows must satisfy to belong to the relation. Its
*extension* — the set of rows currently satisfying the predicate in the
database — is what you read, update, or delete.

## Key features

- **Database-first** — the schema lives in PostgreSQL, not in Python classes.
- **Predicate model** — relations are predicates; set operators (`|`, `&`, `-`)
  compose them before any SQL is sent.
- **FK navigation** — join across tables (and views) by setting FK attributes;
  explicit `Fkeys` dict for views where PostgreSQL stores no FK metadata.
- **Sync + async** — every executor has an `a`-prefixed async counterpart
  (`ho_aselect`, `ho_ainsert`, …).
- **Bulk load** — `ho_copy` / `ho_acopy` for high-throughput inserts via
  PostgreSQL `COPY`.
- **No magic** — queries are built from the predicate you describe and executed
  only when you call an executor. `ho_mogrify()` shows the exact SQL.

## Install

```bash
pip install half_orm
```

Requires **[psycopg 3](https://www.psycopg.org/psycopg3/)** (`psycopg[binary]`).

## Configure

```ini
# ~/.half_orm/blog
[database]
name     = blog
user     = alice
password = secret
host     = localhost
```

## Usage

```python
from half_orm.model import Model
from half_orm.relation_errors import NotFoundError, MultipleRowsError

blog   = Model('blog')
Post   = blog.get_relation_class('blog.post')
Author = blog.get_relation_class('blog.author')

# Insert — returns the inserted row as a dict
alice = Author(
    first_name='Alice', last_name='Martin', email='alice@example.com'
).ho_insert()

# Query — Author(last_name='Martin') is a predicate, not a query
for row in Author(last_name='Martin').ho_select('id', 'email'):
    print(row)

# Get exactly one row
try:
    author = Author(last_name='Martin').ho_get()
except NotFoundError:
    print("no such author")
except MultipleRowsError:
    print("ambiguous — more than one author named Martin")

# FK navigation — no JOIN written by hand
post = Post(id=1)
post.author_fk.set()                         # join all authors
for row in post.ho_select(json_agg={'author_fk': ['first_name', 'last_name']}):
    print(row['author_fk'])                  # {'first_name': 'Alice', 'last_name': 'Martin'}

# Set operators — compose predicates before hitting the database
recent   = Post(created_at=('>', '2024-01-01'))
featured = Post(featured=True)
combined = recent | featured                 # UNION
print(combined.ho_count())

# Update / delete
Author(id=alice['id']).ho_update(email='alice@newdomain.com')
Author(id=alice['id']).ho_delete()
```

## Documentation

- [Learn halfORM in half an hour](https://half-orm.github.io/half-orm/dev/half-an-hour/)
- [API Reference](https://half-orm.github.io/half-orm/dev/api/relation/)

## Extensions

| Extension | Description |
|-----------|-------------|
| [half-orm-dev](https://github.com/half-orm/half-orm-dev) | Development tools — `half_orm dev` project scaffolding, patch management, and schema synchronisation. |

## License

halfORM is licensed under the [GPL-3.0](LICENSE) license.