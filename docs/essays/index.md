# Relation-Oriented Programming

Six essays on why halfORM is built the way it is.

I started building [halfORM](https://github.com/half-orm/half-orm), a Python
library for PostgreSQL, in 2015. Since 2018 we've been using it in production at
work, on several projects.

The reference documentation says what halfORM does. These pages say why the
design takes the shape it does, and what it refuses to do. They are an argument,
not a tutorial: each one takes a known failure mode of object-relational mapping
and shows what happens to it when the schema, rather than the application, holds
authority over the structure of the data access layer.

The thesis, in one sentence: the structural problems of ORM follow from a design
*direction* rather than from implementation quality, and inverting the direction
makes them impossible rather than merely manageable.

Each essay stands on its own. Read them in order for the argument, or pick the
one that names a problem you have.

## The series

| | Essay | What it covers |
|---|---|---|
| 1 | [The Vietnam of Computer Science, Twenty Years On](vietnam-twenty-years-on.md) | Ted Neward's 2006 diagnosis, the seven failure modes it catalogues, and why twenty years of engineering has not dissolved them. |
| 2 | [A Relation Is a Predicate, Not an Object](relation-as-predicate.md) | The core abstraction. Set algebra on Python objects, deferred execution, and what happens to `__eq__` when equality means set equality. |
| 3 | [You Can't Have an N+1 Problem if Navigation Isn't a Query](navigation-is-a-join.md) | Foreign-key navigation as join construction, with no configuration and no fetch strategy to tune. |
| 4 | [Delete Your Repository Layer](predicate-locality.md) | Predicate locality: why query logic can live on the relation class once there is no session, and what that does to code organisation. |
| 5 | [halfORM vs SQLAlchemy Core vs Django ORM](comparison.md) | Three queries side by side, including the one where halfORM loses. |
| 6 | [Git Is the Migration Tool](git-is-the-migration-tool.md) | Schema and code in one commit, patches in plain SQL, and a repository checkout that carries the database itself, not instructions for rebuilding it. |

## The running example

Every essay from part 2 onwards draws on the same four tables. A series
arguing that the schema is the source of truth should start by showing the
schema:

```sql
CREATE TABLE blog.author (
    id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name  TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);

CREATE TABLE blog.post (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title     TEXT NOT NULL,
    content   TEXT,
    published BOOLEAN NOT NULL DEFAULT FALSE,
    author_id UUID REFERENCES blog.author(id)
);

CREATE TABLE blog.comment_type (
    name TEXT PRIMARY KEY
);

CREATE TABLE blog.comment (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content      TEXT NOT NULL,
    post_id      UUID REFERENCES blog.post(id),
    author_id    UUID REFERENCES blog.author(id),
    comment_type TEXT REFERENCES blog.comment_type(name)
);
```

Four foreign keys, three of them converging on `comment`, one lookup table, no
Python. That is the whole model declaration: halfORM introspects it at startup
and the classes named in the essays (`Author`, `Post`, `Comment`, `CommentType`)
are what comes back.

A larger and fully runnable variant, with a second schema for identity, is in
[Simple Blog](../examples/blog.md).

## Scope

These essays argue a position and name its costs. Every one of them states what
the design gives up: no cache, PostgreSQL only, no scalar aggregation without a view,
a migration workflow whose guarantee is procedural rather than structural.

They are not release notes and do not track the API. Where an essay touches
something the reference documentation specifies, it links there;
[Fundamentals](../fundamentals.md) is the authority on the model, and
[Learn halfORM in half an hour](../half-an-hour.md) is the place to start if you
want to write code rather than read an argument.

<!--
  A longer academic treatment of this material exists as a preprint. Add the
  link here once it is deposited, and in the "Scope" paragraph above if it
  deserves the prominence.
-->
