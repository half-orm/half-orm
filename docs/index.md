# halfORM

[![PyPI version](https://img.shields.io/pypi/v/half_orm)](https://pypi.org/project/half-orm/)
[![Python versions](https://img.shields.io/badge/Python-%20≥%203.7-blue)](https://www.python.org)
[![PostgreSQL versions](https://img.shields.io/badge/PostgreSQL-%20≥%209.6-blue)](https://www.postgresql.org)
[![License](https://img.shields.io/pypi/l/half_orm?color=green)](https://pypi.org/project/half-orm/)
[![Tests](https://github.com/half-orm/half-orm/actions/workflows/python-package.yml/badge.svg)](https://github.com/half-orm/half-orm/actions/workflows/python-package.yml)

halfORM is a database-first ORM for PostgreSQL. You write the schema in SQL;
halfORM introspects it at runtime and gives you Python objects to work with your
data. No migrations, no code generation.

**The central idea:** a `Relation` object is a **predicate**. It describes the
logical condition that rows must satisfy to belong to the relation. Its
*extension* — the set of rows that currently satisfy the predicate in the
database — is what you read, update, or delete.

## Install

```bash
pip install half_orm
```

## Configure

```ini
# ~/.half_orm/blog
[database]
name = blog
user = alice
password = secret
host = localhost
```

## Usage

```python
from half_orm.model import Model

blog = Model('blog')
Post   = blog.get_relation_class('blog.post')
Author = blog.get_relation_class('blog.author')

# Insert
alice = Author(
    first_name='Alice', last_name='Martin', email='alice@example.com'
).ho_insert()

# Query — Author(last_name='Martin') is the predicate "is an author named Martin"
for row in Author(last_name='Martin').ho_select('id', 'email'):
    print(row)

# Update a singleton (predicate identifies exactly one row)
Author(id=alice['id']).ho_assert_is_singleton().ho_update(email='alice@newdomain.com')

# Delete
Author(id=alice['id']).ho_assert_is_singleton().ho_delete()
```

## Learn more

- [Learn halfORM in half an hour](half-an-hour.md) — everything you need, in order
- [API Reference](api/relation.md) — every method in detail

## Extensions

| Extension | Description |
|-----------|-------------|
| [half-orm-dev](https://github.com/half-orm/half-orm-dev) | Development tools — `half_orm dev` project scaffolding, patch management, and schema synchronisation. |

