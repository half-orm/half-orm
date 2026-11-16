---
notice: "**1.2.1** fixes a Model that ran its relations under another Model's role, catalog names that reached a statement unquoted, and a transaction that could commit one of its statements alone."
---

# Security advisory — 1.2

**Affected:** 1.2.0 and every release before it, the 1.1, 1.0 and 0.18 lines
included.
**Fixed in:** 1.2.1.

```bash
pip install --upgrade half_orm
```

Found during a second review, of the 1.2.0 release. The first one, a release
earlier, followed input from outside the program to the statement. This one
looked at what halfORM does with things it had reasons to trust — its own
Model objects, the names in the catalog, the connection under a transaction —
and found three places where that trust was carried further than it held.

What halfORM checks, and where the line sits, is on
[the model page](security-model.md), which this release extends.

## A Model ran its relations under another Model's role

Relation classes, and the Model they send their queries through, were shared
by database *name*. A second `Model` opened on the same database under
another role was handed the classes of the first:

```python
admin = Model('blog_admin')        # name = blog, user = admin
ro    = Model('blog_readonly')     # name = blog, user = reader

Post = ro.get_relation_class('blog.post')
Post(id=1).ho_update(title='...')  # ran as admin, and succeeded
```

`ro.execute_query()` did run as `reader`, so the Model looked correctly
restricted to anyone who checked. Its relations were not: every `ho_select`,
`ho_update`, `ho_insert` and `ho_delete` went through the connection of
whichever Model had been created first for that database name. An application
keeping a read-only or per-tenant role next to a privileged one had no such
separation on the relation API — and, created in the other order, a
privileged Model was silently demoted instead.

The metadata cache had the same key, so two servers each holding a database of
the same name shared one catalog description.

Sharing is now decided by what the connection reached and as whom: host, port,
database and role.

## SQL injection through catalog names

Column and type names are read from the catalog and interpolated. Three paths
wrote them without quoting them for what they are:

- **The cast applied to every bound value**, `%s::<type>`, used the type name
  bare. A column whose type is named `int4); select pg_sleep(0); --` — a
  legal name — put exactly that into every query constraining it.
- **Column names** in `WHERE`, `SET`, `INSERT` and `ON CONFLICT` were wrapped
  in quotes without doubling the quotes inside them.
- **The referenced column of a join** was not quoted at all.

halfORM treats the database it connects to as trusted, and creating a type or
a table takes a privilege in it. But that privilege is a lesser one than what
it bought: the injected SQL ran as the role of whichever application
constrained the column, not as the role that had named it. Where a database
is shared between roles of different standing — tenants with a schema each,
an extension installed by someone else — that is an escalation.

## A transaction that committed one statement alone

When a query failed because the connection had dropped, halfORM reconnected
and replayed it. Inside a `Transaction` the statements already sent had gone
with the connection, and the new one is in autocommit mode: the replayed
statement was committed on its own, and no error was raised.

```python
with Transaction(blog):
    debit(account_a)       # lost with the connection
    credit(account_b)      # replayed alone, and committed
```

A connection can be dropped by a restart, a proxy, an idle timeout — or by
anyone allowed to call `pg_terminate_backend`. The error now reaches the
caller and the block rolls back. Outside a transaction the retry is kept.

## A condition that did not mean what it said

`Field.set(('is', value))` rendered `IS NULL` whatever the value, so
`Post(published=('is', True))` selected the posts whose `published` was NULL.
On a read that is a wrong answer; on `ho_update` or `ho_delete` it is the
wrong rows. `IS` now takes `NULL`, `True` or `False` and renders each, and
refuses anything else.

## Guard rails that did not hold

- **`crud_only`** refused `execute_query()` but let `execute_function()` and
  `call_procedure()` through, while their async variants were refused. It is
  a guard rail and not a privilege boundary, but one that was announced as
  leaving "only the Relation CRUD methods".
- **`Model.classes()`** imported a module path built from schema names read
  out of the database, without the checks `_import_class` received in 1.1.0.

## What to do if you cannot upgrade

- **Use one process per role**, or make sure a process only ever creates
  Models of a single role for a given database name. There is no way to keep
  two roles apart inside one process before 1.2.1.
- Do not point halfORM at a database where a role you do not trust may create
  types or tables — or do not constrain the columns of relations such a role
  owns.
- Treat a connection error raised inside a `Transaction` block as *not*
  guaranteeing a rollback: check what was written.
- Replace `('is', True)` and `('is', False)` with `True` and `False`, which
  compare with `=`, minding that `=` does not match NULL the way `IS NOT`
  does.
- Do not rely on `crud_only` to keep functions and procedures out.

## Behaviour changes

Five of these fixes change what a correct program may observe: a class
registered with `@register` no longer crosses from one role to another;
`('is', value)` refuses a value that is not `NULL`, `True` or `False`;
`crud_only` refuses the sync function and procedure calls; a connection lost
inside a transaction raises; and `Model.classes()` reports a module whose own
imports fail. The
[CHANGELOG](https://github.com/half-orm/half-orm/blob/main/CHANGELOG.md)
describes each with what to do about it.

## Credit

Found during an internal review of the 1.2.0 release.
