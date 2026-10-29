# You Can't Have an N+1 Problem if Navigation Isn't a Query

Part 3 of six in *Relation-Oriented Programming*. [Series index](index.md)

The examples use the four-table blog schema of the
[running example](index.md#the-running-example): `author`, `post`,
`comment`, `comment_type`.

Every Python developer who has shipped a Django app has written this bug:

```python
# One query for the posts, then one more per post for the author
for post in Post.objects.filter(published=True):
    print(post.author.name)      # N implicit queries
```

A hundred posts, a hundred and one queries. The fix is well known:

```python
for post in Post.objects.filter(published=True).select_related('author'):
    print(post.author.name)      # one query now
```

Notice what kind of fix that is. It's an **opt-in, at every call site, forever**.
Nothing in the first version is wrong-looking. It reads exactly like the code you
meant to write. The framework chose, on your behalf, to make attribute access
capable of hitting the database, and then handed you a flag to undo that choice
one query at a time. Miss the flag and you get a performance bug that looks like
correct code and only shows up under load.

[Part 2](relation-as-predicate.md) established that a halfORM `Relation` is a
predicate over a set of rows and that nothing touches the database until a
terminal method runs. Apply that to foreign keys and the N+1 problem stops being
a thing you can write.

```python
# One query, with a JOIN. No opt-in, no configuration, no flag to forget.
for row in Post(published=True).fk_author():
    print(row['name'])
```

`fk_author()` does not fetch an author. It returns a new `Relation` on
`blog.author`, restricted to the rows reachable from the current predicate through
that foreign key. It adds a *join constraint*. No SQL is sent. The query runs once,
when iteration begins.

There's no fetch strategy to configure, because there's no fetching to strategise
about. The problem isn't tuned down; it's unreachable.

## Every foreign key is navigable, with no configuration

At startup halfORM introspects the live PostgreSQL catalog: tables, views,
columns, primary keys, foreign-key constraints, inheritance links. That costs a
one-time hit at connection: roughly 19 ms for a four-table schema, 26 ms for
pagila's 23 relations, 384 ms for a GitLab-sized schema of 880 relations.

Out of that metadata, every FK constraint is bound as an instance attribute
under its constraint name, in both directions. If `post` declares a foreign key
to `author`, you get the forward key on `Post` *and* a reverse key on `Author`,
named by convention `_reverse_fkey_<database>_<schema>_<table>_<field>`.
That first component is the database name, which is why `blog` appears twice
below: the database and the schema happen to share a name here. Nothing is
declared in Python. Nothing is configured. Print a bare relation and it tells
you what's available:

```python
>>> print(Author())
# DATABASE: blog | SCHEMA: blog | TABLE: author
# FIELDS:
# - id:    (uuid) NOT NULL
# - name:  (text) NOT NULL
# - email: (text) NOT NULL
# PRIMARY KEY (id)
# FOREIGN KEYS:
# - _reverse_fkey_blog_blog_comment_author_id: ("id")
# - _reverse_fkey_blog_blog_post_author_id: ("id")
#
# Fkeys = {
#     'rfk_blog_blog_comment_author_id': '_reverse_fkey_blog_blog_comment_author_id',
#     'rfk_blog_blog_post_author_id': '_reverse_fkey_blog_blog_post_author_id',
# }
```

That last block is a ready-to-paste template. Copy it into the class body, rename
the keys to something you'd actually want to type, drop the ones you don't need:

```python
class Author(...):
    Fkeys = {
        'rfk_posts': '_reverse_fkey_blog_blog_post_author_id',
    }

class Post(...):
    Fkeys = {
        'fk_author':    'post_author_id_fkey',
        'rfk_comments': '_reverse_fkey_blog_blog_comment_post_id',
    }
```

The convention is `fk_` for a direct, many-to-one key and `rfk_` for a reverse,
one-to-many key, but it's only a convention; pick your own names. And aliases
are strictly optional ergonomics. `author.rfk_blog_blog_post_author_id()` works from
the moment you instantiate the model; `author.rfk_posts()` is the same thing
with a name you enjoy reading.

This is the part that's hard to appreciate until you've used it. There is no model
file. There is no `Table(...)` per relation, no `models.ForeignKey(...)`, no
mapping configuration, no `relationship()` with a `back_populates`. The schema
already says all of that. It said it in DDL, which is the language for saying it.

## Chained navigation is still one query

```python
author = Author(name='Alice')

# Authors who have commented on Alice's posts: one query, three joins
author.rfk_posts().rfk_comments().fk_author()
```

Each step extends the relational expression. Nothing executes. The join conditions
come from the FK constraints recorded in the catalog, so there is nothing to state
and nothing to get wrong.

Combine that with the set operators from part 2 and the expressions start
reading like the question you were asked:

```python
# Authors who have commented but never written a post
Comment().fk_author() - Post().fk_author()

# Authors who have both posted and commented
Post().fk_author() & Comment().fk_author()

# Authors who commented on published posts
Post(published=True).rfk_comments().fk_author()
```

No Python loop anywhere. Each of those is one SQL query.

FK aliases also take keyword arguments, so a join and an additional filter on the
target are a single expression:

```python
post.fk_author(name=('ilike', 'a%'))
```

And crucially, unlike ORM eager loading (which applies a loading strategy across
all mapped associations), only the associations you actually navigate are
joined. Nothing else. The join graph is exactly what you wrote.

## Navigating vs. joining in place

Each FK attribute supports two modes, and the difference matters once you want
nested results.

Calling it (`post.fk_author()`) **navigates**: you get a `Relation` on the
target table and you've moved.

Calling `.set()` on it (`alice.rfk_posts.set()`) **activates the join without
moving**: `alice` is still an `Author` predicate, but the join to `post` is now
live. Which lets `ho_select` aggregate the joined rows:

```python
alice = Author(name='Alice')
alice.rfk_posts.set()

for row in alice.ho_select(json_agg={'rfk_posts': ['id', 'title']}):
    print(row['name'], row['rfk_posts'])
    # row['rfk_posts'] == [{'id': ..., 'title': '...'}, ...]
```

One query. PostgreSQL's `json_agg` does the nesting server-side. The return type
follows the FK direction: a reverse key (one-to-many) gives you a list of dicts, a
direct key (many-to-one) gives you a single dict or `None`.

This covers the nested-retrieval case that would otherwise push you to a view or
to raw SQL: the "give me each author with their posts" shape that classical ORMs
answer with `prefetch_related` and two queries stitched together in Python.

## The honest part: joins make duplicates

SQL operates on multisets. The relational model doesn't. Compose two navigated
expressions with a set operator and the generated SQL can hand you the same row
more than once. Take the published posts written by Alice or by Bob:

```python
published  = Post(published=True)
all_theirs = (Author(name='Alice').rfk_posts() |
              Author(name='Bob').rfk_posts())

result = list((published & all_theirs).ho_select())
# Warning: 3 duplicate(s) removed in ho_select on Post.
#          Consider using distinct=True for better performance.
```

Both operands of the `|` reach `post` by navigating from `author`, so the
intersection carries two paths to the same table, and a post can arrive by both.
halfORM removes duplicates by primary key, so correctness is preserved
regardless, and warns you. Passing `distinct=True` silences the warning and
delegates deduplication to PostgreSQL, which is what you want on a large result
set:

```python
list((published & all_theirs).ho_select(distinct=True))
```

Often there's a formulation that avoids the issue entirely by starting from the
other end. The same question, asked from `author` instead of from `post`:

```python
list(Author(name=('in', ['Alice', 'Bob'])).rfk_posts(published=True))
```

That is one hop from `author` to `post`, so no row can arrive twice. The two
expressions denote the same set and generate structurally different SQL; which
one you write depends on which relation is the natural starting point for the
question.

Two limitations. `DISTINCT` isn't applied automatically everywhere, because
duplicates are sometimes intentional (`ho_count()` especially), so the opt-in
stays explicit. And tables without a primary key, plus views (which have no PK
by definition), can't benefit from PK-based deduplication at all. For those,
rows come back as-is and it's on you to pass `distinct=True`, or on the view
definition to produce a set in the first place.

## You can always see the SQL

Since there's no cache and no query rewriting layer, what you wrote is what runs,
and you can check:

```python
published = Post(published=True)
q = (published.fk_author(name=('ilike', 'alice%')) |
     published.fk_author(name=('ilike', 'john%')))
q.ho_mogrify()
list(q)
# select
#   r1.*
# from
#   "blog"."author" as r1
#   join "blog"."post" as r2 on
#     (r2."author_id" = r1."id")  and
#     (r2."published" = true::bool)
# where
#   ((r1."name" ilike 'alice%'::text) or
#   (r1."name" ilike 'john%'::text))
```

Two navigations combined with `|` produce one join, with `published` folded into
the `ON` clause and the two name predicates merged into a single `WHERE`. Setting
`model.sql_trace = True` logs every query along with the Python file and line that
caused it.

There's also a predicate-level view, before any query exists. `repr()` on a
navigated relation shows the whole join structure, with each target's own
constraints nested inside:

```python
q = published.fk_author(name=('ilike', 'alice%'))
repr(q)
# DATABASE: blog  |  SCHEMA: blog  |  TABLE: author
# FIELDS:
# - id:    (uuid) NOT NULL
# - name:  (text) NOT NULL    (name ilike alice%)
# - email: (text) NOT NULL
# FOREIGN KEYS:
# - _reverse_fkey_blog_blog_post_author_id: ("id")
#      TABLE: post
#      FIELDS:
#      - id:        (uuid) NOT NULL
#      - title:     (text) NOT NULL
#      - published: (bool) NOT NULL  (published = True)
#      - author_id: (uuid)
```

You can read the query you're about to run without running it.

Since every predicate compiles to plain parameterised SQL over psycopg3, there's
no runtime overhead relative to hand-written queries. Performance is PostgreSQL
and the network. The only framework cost is that one-time introspection at
startup.

## The general shape

An N+1 problem requires that traversing a relationship be capable of issuing a
query. Remove that capability and the bug class goes with it: not as a default
you could change, not as a lint rule, not as a flag you have to remember. There
is no code you can write that produces it.

That's what "structurally precluded" means, and it's the same move as the last
post's: don't solve the problem, remove the concept it needs in order to exist.

Next: what this does to the *shape* of a codebase, specifically why the
Repository pattern stops earning its keep.

---

*Foreign-key navigation is documented in [FKey](../api/fkey.md), and worked through end to end in [Simple Blog](../examples/blog.md).*
