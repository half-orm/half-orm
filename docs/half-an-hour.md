# Learn halfORM in half an hour

halfORM is a database-first ORM for PostgreSQL. You write the schema in SQL;
halfORM introspects it at runtime and gives you Python objects to work with your
data. No migrations, no code generation.

**The central idea:** a `Relation` object is a **predicate**. It describes the
logical condition that rows must satisfy to belong to the relation. Its
*extension* — the set of rows that currently satisfy the predicate in the
database — is what you read, update, or delete.

Adding a constraint specialises the predicate. Set operators (`|`, `&`, `-`)
are logical operators on predicates. Foreign key navigation composes predicates
across tables.

This guide covers everything you need, in order.

---

## Schema used in this guide

```sql
create schema blog;

create table blog.author (
    id         serial primary key,
    first_name text not null,
    last_name  text not null,
    email      text unique not null
);

create table blog.post (
    id        serial primary key,
    title     text not null,
    content   text,
    author_id integer references blog.author(id) on delete cascade
);

create table blog.comment (
    id        serial primary key,
    content   text not null,
    post_id   integer references blog.post(id) on delete cascade,
    author_id integer references blog.author(id) on delete cascade
);
```

---

## 1. Connect (1 min)

halfORM reads connection parameters from `~/.half_orm/<dbname>`:

```ini
# ~/.half_orm/blog
[database]
name = blog
user = alice
password = secret
host = localhost
```

```python
from half_orm.model import Model

blog = Model('blog')
print(blog)
```

```
📋 Available relations for blog:
r "blog"."author"
r "blog"."comment"
r "blog"."post"
```

Get a class for a table with [`get_relation_class()`](api/model.md#half_orm.model.Model.get_relation_class) — each class represents the **set of all rows** in that table:

```python
Author  = blog.get_relation_class('blog.author')
Post    = blog.get_relation_class('blog.post')
Comment = blog.get_relation_class('blog.comment')
```

Print a class to inspect its schema (columns, types, constraints, foreign keys):

```python
print(Author())
```

---

## 2. A Relation is a predicate

Instantiating with keyword arguments **specialises the predicate** by adding
conditions. No argument → the tautology "is a row of this table" (the whole
table). Each argument adds a conjunct.

```python
Author()                              # predicate: "is an author"             → all rows
Author(last_name='Martin')            # predicate: "is an author named Martin" → subset
Author(last_name='Martin', id=42)     # predicate: "Martin with id 42"         → at most one row
```

The object does not query the database. It holds a predicate. The query happens
only when you explicitly ask for the extension (via [`ho_select`](api/relation.md#half_orm.relation.Relation.ho_select), [`ho_count`](api/relation.md#half_orm.relation.Relation.ho_count), etc.).

This is the foundation everything else builds on.

---

## 3. Query the extension (5 min)

### Cardinality

```python
Author().ho_count()                        # cardinality of "is an author"
Author(last_name='Martin').ho_count()      # cardinality of "is an author named Martin"
Author(last_name='Unknown').ho_is_empty()  # True if the extension is empty
```

### Enumerate the extension

[`ho_select()`](api/relation.md#half_orm.relation.Relation.ho_select) is a generator that yields each row as a dict. Without arguments
it is equivalent to iterating directly on the relation:

```python
for row in Author():                  # equivalent to Author().ho_select()
    print(row['first_name'], row['last_name'])
```

Pass field names to project only certain columns:

```python
for row in Author(last_name='Martin').ho_select('id', 'email'):
    print(row)   # {'id': 1, 'email': 'alice@example.com'}
```

Control ordering and size of the result set:

```python
for row in Author().ho_select(order_by='last_name', limit=10, offset=20):
    print(row)
```

### Comparators

Equality is the default. For anything else, pass a `(operator, value)` tuple:

```python
Author(last_name=('like', 'Mar%'))       # set where last_name LIKE 'Mar%'
Author(last_name=('ilike', 'mar%'))      # case-insensitive
Author(id=('>', 10))                     # set where id > 10
Author(id=('in', [1, 2, 3]))             # set where id IN (1, 2, 3)
```

### NULL values

Python `None` *unsets* a constraint (no effect on the set definition).
Use `half_orm.null.NULL` to build the set of rows where a column is NULL:

```python
from half_orm.null import NULL

Post(content=NULL)                       # set where content IS NULL
Post(content=('is not', NULL))           # set where content IS NOT NULL
```

---

## 4. Insert: add an element to a table (2 min)

[`ho_insert()`](api/relation.md#half_orm.relation.Relation.ho_insert) inserts the row described by the object's constraints and returns
the inserted row as a dict:

```python
row = Author(
    first_name='Alice',
    last_name='Martin',
    email='alice@example.com',
).ho_insert()

print(row)   # {'id': 1, 'first_name': 'Alice', 'last_name': 'Martin', ...}
```

---

## 5. Singleton predicate (2 min)

A predicate is a **singleton** when it logically identifies at most one row —
i.e. a primary key or unique NOT NULL constraint is fully specified with `=`.

[`ho_assert_is_singleton()`](api/relation.md#half_orm.relation.Relation.ho_assert_is_singleton) verifies this *without querying the database* and
returns `self` for chaining. It raises `NotASingletonError` if the predicate
is not a singleton.

```python
Author(id=42).ho_assert_is_singleton()          # OK — id is the PK
Author(email='alice@example.com').ho_assert_is_singleton()  # OK — email is UNIQUE NOT NULL
Author(last_name='Martin').ho_assert_is_singleton()         # raises: last_name is not unique
```

Use it as a guard before any single-row write:

```python
Author(id=42).ho_assert_is_singleton().ho_update(email='alice@newdomain.com')
Author(id=99).ho_assert_is_singleton().ho_delete()
```

---

## 6. Update: transform the extension (1 min)

[`ho_update()`](api/relation.md#half_orm.relation.Relation.ho_update) modifies every row that satisfies the predicate:

```python
# Update one row — guarded
Author(id=1).ho_assert_is_singleton().ho_update(email='alice@newdomain.com')

# Update a whole subset at once
Post(author_id=99).ho_update(content='[archived]')
```

---

## 7. Delete: remove the extension (1 min)

[`ho_delete()`](api/relation.md#half_orm.relation.Relation.ho_delete) removes every row that satisfies the predicate:

```python
Author(id=99).ho_assert_is_singleton().ho_delete()

# delete_all=True is required when no primary key field is set
# — a deliberate safety guard against accidental mass deletions.
Post(author_id=1).ho_delete(delete_all=True)
```

---

## 8. Foreign keys: composing predicates across tables (10 min)

### `@register` — make your subclass the default

`blog.get_relation_class('blog.post')` returns a generated base class. When you
subclass it, halfORM still uses the base class for FK navigation unless you
register your subclass:

```python
from half_orm.model import register

@register
class Post(blog.get_relation_class('blog.post')):
    ...
```

`@register` tells the Model to use `Post` everywhere that table appears — FK
navigation returns *your* class, with your aliases and methods, not the
generated base class. **Always decorate relation subclasses with `@register`.**

### Naming FK attributes

halfORM exposes every foreign key, but auto-generated names are long. Give them
friendly aliases in a `Fkeys` class attribute:

```python
@register
class Post(blog.get_relation_class('blog.post')):
    Fkeys = {
        'author_fk':   'post_author_id_fkey',                  # FK → author
        'comment_rfk': '_reverse_fkey_blog_comment_post_id',   # ← comment
    }

@register
class Author(blog.get_relation_class('blog.author')):
    Fkeys = {
        'post_rfk':    '_reverse_fkey_blog_post_author_id',
        'comment_rfk': '_reverse_fkey_blog_comment_author_id',
    }

@register
class Comment(blog.get_relation_class('blog.comment')):
    Fkeys = {
        'post_fk':   'comment_post_id_fkey',
        'author_fk': 'comment_author_id_fkey',
    }
```

!!! tip "Finding FK names"
    `print(Post())` lists all foreign keys with their internal names.

### [`fkey()`](api/fkey.md#half_orm.fkey.FKey.__call__) — extend the predicate into a related table

Calling a FK attribute produces a new predicate on the related table, restricted
to the rows linked to the current predicate's extension:

```python
post   = Post(id=1)
author = post.author_fk()           # predicate: "is the author of post 1"

posts_by_martin = Author(last_name='Martin').post_rfk()
                                    # predicate: "is a post written by a Martin"
```

The result is itself a predicate — keep composing it:

```python
# "is a post written by a Martin with non-empty content"
martin_posts = Author(last_name='Martin').post_rfk(content=('is not', NULL))
print(martin_posts.ho_count())
```

### [`fkey.set(predicate)`](api/fkey.md#half_orm.fkey.FKey.set) — compose predicates across a join

`.set()` adds a join condition: the rows satisfying the current predicate must
also be linked to rows satisfying the given predicate in another table.
halfORM generates the JOIN automatically.

```python
# "is a post whose author satisfies last_name LIKE 'Mar%'"
post = Post()
post.author_fk.set(Author(last_name=('like', 'Mar%')))
print(post.ho_count())
```

Chain as many `.set()` calls as needed:

```python
# "is a comment whose post was written by a 'Mar%' author"
comment = Comment()
post    = Post()
post.author_fk.set(Author(last_name=('like', 'Mar%')))
comment.post_fk.set(post)

print(comment.ho_count())
```

### `json_agg` — attach a related predicate's extension as a JSON column

```python
# For each author named Martin, their posts (id + title) as a JSON array
alice = Author(last_name='Martin')
alice.post_rfk.set(Post())

for row in alice.ho_select(json_agg={'post_rfk': ['id', 'title']}):
    # row['post_rfk'] = [{'id': 1, 'title': '...'}, ...]
    print(row['last_name'], row['post_rfk'])
```

Empty list = all fields. Optional `'alias'` key renames the output column:

```python
alice.ho_select(json_agg={
    'post_rfk': {'fields': ['id', 'title'], 'alias': 'posts'}
})
```

---

## 9. Predicate algebra (5 min)

Predicates compose. The four logical operators map directly to Python operators —
the result is always a new predicate.

```python
martins  = Author(last_name='Martin')
gmail    = Author(email=('ilike', '%@gmail.com'))

martins | gmail   # disjunction:  "is a Martin" OR "has a gmail address"
martins & gmail   # conjunction:  "is a Martin" AND "has a gmail address"
martins - gmail   # difference:   "is a Martin" AND NOT "has a gmail address"
-martins          # negation:     NOT "is a Martin"
```

Every result is a predicate — query its extension like any other:

```python
for row in (martins | gmail).ho_select('first_name', 'last_name', 'email'):
    print(row)

(martins - gmail).ho_count()
```

Compose freely:

```python
# "is a post with content whose title does not contain 'draft'"
relevant = (
    Post(content=('is not', NULL)) &
    -Post(title=('ilike', '%draft%'))
)
print(relevant.ho_count())
```

---

## 10. Transactions (5 min)

[`Transaction`](api/transaction.md#half_orm.transaction.Transaction) is a context manager that wraps operations in a single atomic unit.
It commits on success, rolls back on exception.

```python
from half_orm.transaction import Transaction

with Transaction(blog):
    alice_row = Author(
        first_name='Alice', last_name='Martin', email='alice@example.com'
    ).ho_insert()

    Post(
        title='First post',
        content='Hello world',
        author_id=alice_row['id'],
    ).ho_insert()

# Both rows are committed, or neither is.
```

Transactions nest — inner `Transaction` blocks use savepoints automatically:

```python
with Transaction(blog):
    alice_row = Author(...).ho_insert()

    with Transaction(blog):            # savepoint
        Post(...).ho_insert()
        # exception here rolls back only the post, not Alice
```

---

## 11. Custom classes and business logic (2 min)

Put methods on your relation classes to encapsulate logic that belongs to a
predicate:

```python
from half_orm.relation import singleton

@register
class Author(blog.get_relation_class('blog.author')):
    Fkeys = {
        'post_rfk': '_reverse_fkey_blog_post_author_id',
    }

    @singleton
    def publish(self, title: str, content: str):
        """Add a post to the set defined by self (must be a singleton)."""
        return self.post_rfk(title=title, content=content).ho_insert()
```

[`@singleton`](api/relation.md#half_orm.relation.singleton) calls [`ho_assert_is_singleton()`](api/relation.md#half_orm.relation.Relation.ho_assert_is_singleton) automatically — no DB round-trip,
pure predicate check:

```python
alice = Author(id=1)
alice.publish('My post', 'Content here')   # @singleton verifies alice is a singleton predicate
```

---

## Quick reference

| Goal | Code |
|------|------|
| Connect | [`Model('dbname')`](api/model.md#half_orm.model.Model) |
| Tautological predicate (whole table) | [`model.get_relation_class('schema.table')`](api/model.md#half_orm.model.Model.get_relation_class) |
| Specialise a predicate | `Rel(field=val, ...)` |
| Cardinality of the extension | [`rel.ho_count()`](api/relation.md#half_orm.relation.Relation.ho_count) |
| Enumerate the extension | [`rel.ho_select('col1', 'col2')`](api/relation.md#half_orm.relation.Relation.ho_select) |
| Add a row | [`Rel(col=val).ho_insert()`](api/relation.md#half_orm.relation.Relation.ho_insert) |
| Update the extension | [`Rel(pred).ho_update(col=new_val)`](api/relation.md#half_orm.relation.Relation.ho_update) |
| Delete the extension | [`Rel(pred).ho_delete()`](api/relation.md#half_orm.relation.Relation.ho_delete) |
| Assert singleton predicate (no DB) | [`Rel(pk=val).ho_assert_is_singleton()`](api/relation.md#half_orm.relation.Relation.ho_assert_is_singleton) |
| Compose into related table | [`obj.fk_attr()`](api/fkey.md#half_orm.fkey.FKey.__call__) |
| Compose via join | [`obj.fk_attr.set(OtherRel(...))`](api/fkey.md#half_orm.fkey.FKey.set) |
| Aggregate related extension | [`obj.ho_select(json_agg={'fk_attr': ['col', ...]})`](api/relation.md#half_orm.relation.Relation.ho_select) |
| Disjunction / conjunction / difference / negation | `a &#124; b`, `a & b`, `a - b`, `-a` |
| Atomic operations | [`with Transaction(model):`](api/transaction.md#half_orm.transaction.Transaction) |
| SQL NULL | `from half_orm.null import NULL` |
| Inspect generated SQL | `model.sql_trace = True` |

---

**Next:** the [API reference](api/relation.md) documents every method in detail.