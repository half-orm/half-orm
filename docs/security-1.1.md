---
notice: "**1.1.0** fixes several ways an identifier could reach a statement unchecked, a transaction that committed instead of rolling back, and a CLI extension trust mechanism that enforced less than it displayed."
---

# Security advisory — 1.1

**Affected:** 1.0.0 and every release before it.
**Fixed in:** 1.1.0, released 2026-09-11.

```bash
pip install --upgrade half_orm
```

Found during a review of the 1.0.0 release. The defects below all share one
shape: data from outside the program reached a query, a file path or an import
as *code* rather than as data. The most reachable of them need no unusual
integration — a CSV header, the keys of a JSON body, or a checked-out
repository are enough.

## SQL injection through identifiers

Several paths interpolated caller-supplied names into the statement without
checking them against the schema, and without escaping. Why identifiers are
interpolated at all, and which ones are checked today, is on
[the model page](security-model.md).

- **`ho_copy()` and `ho_acopy()`** took column names from a CSV header or from
  the keys of the caller's dicts. A header of
  `last_name") from stdin; create table public.pwned(x int); --` closed the
  identifier and the statement and ran the rest. An uploaded CSV or a
  deserialised request body reaches this directly.
- **`Field.set()` comparators** were interpolated, not bound:
  `last_name=('or 1=1 --', 'x')` produced `(r1."last_name" or 1=1 -- %s)`. On
  `ho_delete()` that turns a targeted statement into a global one, and the
  `delete_all` safeguard does not fire, because the field *is* technically
  constrained.
- **`order_by`** went into the query as given. No semicolon is needed to abuse
  it: `ORDER BY` accepts a subquery, so one bit of someone else's data comes
  back per request. It is also the parameter most likely to be wired straight
  to a query string (`?sort=`).
- **The `json_agg` projection** interpolated five caller-supplied slots
  unchecked, including `alias` and `ho_select`'s own `*args`.
- **Function and procedure names**, and the keys of named parameters, were
  interpolated by `execute_function()` and `call_procedure()`.
- **Relation names** were quoted without escaping the quotes inside them, and
  `get_relation_class` stripped every quote before splitting, so two distinct
  schemas answered for one another.

## Arbitrary code execution through CLI extensions

The `half_orm` CLI imports installed `half-orm-*` packages, which runs them. Its
consent prompt was suppressed by a `.half_orm_cli` file read from the *current
directory*, so a repository shipping that file granted itself silent consent:
clone, run `half_orm`, and the extension executed while the CLI reported
`[TRUSTED]`. A `git clone` produces files owned by you, so no ownership or
permission check could have closed this.

Two related defects: `--trusted-extensions` and `--untrust` were parsed after
the extensions had already loaded, so they could change nothing; and the
allowlist named a PyPI project nobody had registered, granting automatic trust
to whoever claimed it.

## Module loading driven by database content

`Model._import_class()` built an import path from a relation's schema and name
— values read from the database — and passed it to `__import__`. Importing a
module runs it. A bare `except:` then hid any error the imported module raised,
including errors in your own code.

## Path traversal in the connection file name

`Model(config_file)` takes a file *name*, but joined it to `CONF_DIR` without
confining it: `..` climbed out and an absolute path discarded `CONF_DIR`
entirely. That decides which database, and as which role, the process connects.
The guard refusing a reconnect to a different database also covered only one of
two branches.

## Loss of committed work

`Transaction.__exit__` committed unconditionally at the outermost level, so a
Python exception crossing the block committed the partial work instead of
discarding it. It went unnoticed because the tests raised `UniqueViolation`,
where PostgreSQL has already aborted the transaction and COMMIT behaves as
ROLLBACK; it only bit on non-SQL exceptions.

## Information disclosure

Failed queries logged their parameter values — passwords, session tokens and
personal data reaching application logs on every constraint violation. Relation
aliases embedded `id(self)`, a heap address, in every statement, and so in logs
and `pg_stat_statements`.

## What to do if you cannot upgrade

None of these have a workaround that covers the set. Until you can upgrade:

- never pass externally-derived values as column names, comparators, `order_by`
  clauses, function names or connection file names;
- do not run `half_orm` from a directory you did not author, and delete any
  `.half_orm_cli` you did not write yourself;
- treat the database you connect to as trusted, since its schema names select
  Python modules to import.

## Behaviour changes

Six of these fixes turn something that used to pass silently into an error, and
one changes how a configuration file is read. The
[CHANGELOG](https://github.com/half-orm/half-orm/blob/main/CHANGELOG.md)
describes each with what to do about it. The one most likely to affect a
running system: `production = false` was being read as **true**, and now means
what it says.

## Credit

Found during an internal review of the 1.0.0 release.
