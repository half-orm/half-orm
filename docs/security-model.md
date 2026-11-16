# What halfORM defends, and what it cannot

halfORM stands between your application and PostgreSQL. Some of what keeps a
statement safe is its work, and some of it is yours. This page draws that line.
It does not change from one release to the next; the
[advisories](security.md) record the times something was found on the wrong
side of it.

## Values are bound, identifiers are not

One rule explains most of what follows. PostgreSQL parameterises *values*, and
has no parameter for an *identifier* — a column, relation or function name.
Values are therefore handed to the server separately from the statement, and
identifiers are written into its text.

```python
# The value is bound. Nothing this string contains can change the statement --
# it is compared against the column, never parsed as SQL.
Author(last_name=untrusted).ho_select()
```

So a value from a request, a file or another system is safe as a value. A name
is a different matter, and that is where halfORM does its checking.

## What halfORM checks for you

Since 1.1.0, every identifier halfORM interpolates is either checked against the
schema it introspected or constrained to a grammar that cannot close the
statement:

| What | How it is checked |
| --- | --- |
| Column names (`ho_select`, `ho_update`, `ho_insert`, `ho_copy`) | Must exist on the relation; quoted on the way out |
| Type names (the `::type` cast applied to a bound value) | Read from the catalog; quoted unless a plain lower-case identifier |
| `order_by` | Parsed as a list of columns with an optional direction and `NULLS` placement; each column checked against the relation. An expression, a qualified name or a second statement is refused |
| `Field.set()` comparators | A listed word operator (`like`, `is not`, `in`, …) or an operator spelled only with PostgreSQL's operator characters — never a space, a quote or a comment opener |
| `json_agg` projections | Same checks as the plain `ho_select` path |
| Relation and schema names | Quoted, with embedded quotes doubled |
| Function and procedure names | Must be a SQL name, optionally schema-qualified (see below) |

A name that fails one of these raises `ValueError` or `UnknownAttributeError`
rather than reaching the database.

## A relation runs as the role of its Model

A `Model` is a connection: a server, a database and a role. A relation class
obtained from it — through `get_relation_class`, foreign-key navigation or a
generated package — sends its queries through that Model, and so with that
role's privileges and no one else's.

```python
admin = Model('blog_admin')        # name = blog, user = admin
ro    = Model('blog_readonly')     # name = blog, user = reader

Post = ro.get_relation_class('blog.post')
Post(id=1).ho_update(title='...')  # refused by PostgreSQL: reader cannot write
```

Models are told apart by host, port, database and role, as the connection
reports them. Two Models that agree on all four share their relation classes,
`@register`-ed ones included; two that differ on any share nothing, the
catalog description aside when only the role differs. So a restricted Model
kept next to a privileged one stays restricted, in whatever order they were
created.

Two limits follow from a Model *being* a connection rather than holding one
per caller:

- `Model.reconnect(config_file)` changes the role of that Model, and with it
  the role of every class already bound to it. The calling thread switches at
  once; the other threads keep the connection they hold and pick up the new
  role whenever they next open one. It is therefore not a way to run one
  request as another role while other threads carry on: use one Model per
  role instead.
- The role is the one the connection was opened as. A `SET ROLE` issued
  through `execute_query` is invisible to halfORM, and applies only to the
  connection of the thread that issued it.

The privileges themselves are PostgreSQL's. halfORM routes a query to the
right role; what that role may do is decided by `GRANT` and `REVOKE`.

## What halfORM cannot check for you

Two things are constrained but not resolved, and the difference matters if you
build them from input you do not control.

**Function and procedure names.** `Model.execute_function()` and
`call_procedure()` bind their arguments, and check the callable's name to *be* a
name — it cannot carry a space, a parenthesis or a quote, so it cannot end the
call and start something else. But the name is not looked up against the
catalog. An attacker who chooses it cannot inject SQL; they can still choose
**which function runs**, among those your role may call.

```python
# No injection is possible -- and the caller still picks the function.
model.execute_function(f'admin.{request["action"]}', user_id)   # don't
```

**Connection file names.** `Model(config_file)` takes a file *name*, and since
1.1.0 refuses anything that looks like a path, so it cannot climb out of
`HALFORM_CONF_DIR`. It is still free to name any file *inside* it — and that
file decides which database the process connects to, and as which role. In a
multi-tenant application picking a connection per tenant, map the tenant to a
name you control rather than passing the request's value through.

## Trusted by design

Two things are part of halfORM's trusted computing base. Neither is a defect;
both are worth knowing.

**The database you connect to.** Its schema and relation names drive class
generation and module loading, and its structure is read as authoritative.
halfORM does not treat the database as untrusted input to be sanitised.

**Installed CLI extensions.** The `half_orm` command imports them, and importing
runs them. Unofficial extensions are approved per project and pinned to a digest
of their code, so republished code is not covered by an old approval — but an
extension you approve runs with your privileges. See
[Extensions](extensions/index.md) for how approval works and where it is
recorded.

Reports about either are still welcome. The boundaries above are where we think
the line is, not a list of things we refuse to look at.
