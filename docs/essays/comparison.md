# halfORM vs SQLAlchemy Core vs Django ORM

Part 5 of six in *Relation-Oriented Programming*. [Series index](index.md)

Let me declare the bias first: I wrote halfORM. Everything below is a structural
comparison chosen to illustrate a design claim, not a neutral evaluation of three
libraries. There's no benchmark here and no user study. I've included the case
where halfORM comes off worst, because a comparison that only shows wins isn't
worth reading.

The two reference points are the dominant styles of Python data access.
SQLAlchemy Core is a SQL expression builder and the closest structural peer
here, since both defer execution and compose expressions. Django ORM is the full
code-first ORM. Peewee, PonyORM and Tortoise are all code-first with model class
declarations and condition-level composition, so they'd sit next to Django in
every row below.

All examples use a four-table blog schema: `author`, `post`, `comment`,
`comment_type`, whose DDL is in the
[series index](index.md#the-running-example). In the SQLAlchemy listings, `post` / `author` / `comment` are
`Table` objects declared with `autoload_with=engine`.

The underlying difference is what the *composable unit* is:

- SQLAlchemy Core composes **column expressions** (`post.c.published == True`)
  and `Select` statements.
- Django ORM composes **`Q` objects** and `__` path expressions.
- halfORM composes **relation predicates**: an object carrying its table, its
  constraints, and its join structure.

That distinction sounds academic until you try to reuse something.

## Query 1: set difference

*Authors who have never posted.*

halfORM:

```python
Author() - Post().fk_author()
```

SQLAlchemy Core, with no set-difference operator on `Select` objects, needs a
subquery:

```python
select(author).where(
    ~author.c.id.in_(
        select(post.c.author_id).where(post.c.author_id.isnot(None))
    )
)
```

Django ORM has no set-difference operator either; `exclude` with a subquery:

```python
Author.objects.exclude(id__in=Post.objects.values('author_id'))
```

All three work. The difference is that one of them is the relational operation
you actually meant, written once, with a `-`.

## Query 2: predicate reuse

This is the one that matters.

In halfORM a `Relation` is a value. Name it, store it, pass it around, compose
it into different things; no query runs until a terminal method does:

```python
published   = Post(published=True)               # a value
alice_posts = Author(name='Alice').rfk_posts()   # a value

published & alice_posts                # published posts by Alice
published.rfk_comments().fk_author()   # commenters on published posts
```

`published` is reused in two structurally different queries. It carries its own
join structure, so nothing has to be restated.

SQLAlchemy Core: `published_cond` is a *column expression*. It carries no join
structure. Each reuse restates the joins:

```python
published_cond = post.c.published == True

# Reuse 1: join restated
select(post).join(author, post.c.author_id == author.c.id) \
            .where(and_(published_cond, author.c.name == 'Alice'))

# Reuse 2: two joins restated
select(author).join(comment, comment.c.author_id == author.c.id) \
              .join(post, comment.c.post_id == post.c.id) \
              .where(published_cond)
```

Django `Q` objects are composable and their `__` paths do resolve to joins, but
the join structure comes from the `QuerySet` context, not from the `Q` object. A
`Q` written for one starting relation can't cross over to another:

```python
published = Q(published=True)
alice_q   = Q(author__name='Alice')

Post.objects.filter(published & alice_q)               # context 1: fine
Author.objects.filter(comment__post__published=True)   # context 2: `published`
                                                       # cannot be reused here
```

The halfORM version of that second query is
`published.rfk_comments().fk_author()`: the same `published` object, in a
different composition.

## Query 3: multi-hop navigation

*Authors who commented on published posts.*

halfORM, with no join conditions at all, because they're in the catalog:

```python
Post(published=True).rfk_comments().fk_author()
```

SQLAlchemy Core, with every join condition explicit:

```python
select(author) \
    .join(comment, comment.c.author_id == author.c.id) \
    .join(post, comment.c.post_id == post.c.id) \
    .where(post.c.published == True)
```

Django is concise, and the `filter` itself generates a single JOIN query:

```python
authors = Author.objects.filter(comment__post__published=True)
```

Credit where due: that's a good line. The problem is downstream, when you traverse
the results:

```python
for author in authors:
    for comment in author.comment_set.all():   # N queries
        print(comment.post.title)              # N more queries

# Fix: explicit opt-in, restating the full traversal path
Author.objects.filter(comment__post__published=True) \
              .prefetch_related('comment_set__post')
```

Both Django ORM and SQLAlchemy's ORM layer return model instances rather than
dictionaries, which brings back the identity, session, and lazy-loading
questions from [part 1](vietnam-twenty-years-on.md) of this series.

## Summary

What the developer must state explicitly:

| | Set difference | Predicate reuse | Multi-hop | Schema declaration | Result type | N+1 by default |
|---|---|---|---|---|---|---|
| **halfORM** | `-` operator | compose once | 0 join conditions | none | dicts | not expressible |
| **SQLAlchemy Core** | subquery | restate joins | explicit joins | `Table` per relation | dicts | no |
| **Django ORM** | `filter`/`exclude` | restate path | `__` traversal | model class | model instances | yes, unless prefetch |

The "schema declaration" column is the one that compounds. SQLAlchemy Core with
`autoload_with` populates column metadata from the live database automatically,
but you still need one `Table` variable per relation and you still write join
conditions by hand. `automap_base()` goes further and generates mapped classes
from a live schema, but it targets the ORM layer, so what you get back carries
the identity map, the session, and the lazy loading that this whole design is
trying to avoid. halfORM's database-first stance isn't unique; the combination
of introspection-only, relation-level predicates, and no session management
doesn't have a direct equivalent in the Python ecosystem that I know of.

## Where halfORM loses: scalar aggregation

Two things travel under the name "aggregation", and halfORM handles exactly one
of them.

**Collecting related rows** it does natively. `ho_select(json_agg=...)`, from
[part 3](navigation-is-a-join.md), compiles to a `LEFT JOIN` plus `json_agg`
plus a `GROUP BY` on the primary key, and returns each author with their posts
nested inside the row. It follows FK chains, and takes a `distinct` flag for
when an intermediate join multiplies rows. No view required.

**Reducing them to one number per group** it does not. Annotate every author
with their post count. Django:

```python
Author.objects.annotate(post_count=Count('post'))
```

One expression. Django infers the `LEFT OUTER JOIN` and the `GROUP BY` from the
declared foreign key. It's exactly right, and it's the kind of thing you write
constantly.

halfORM has no equivalent. There is no `COUNT`, `SUM` or `AVG` to project per
group, no `HAVING` to filter on the result, and no window functions;
correlated subqueries are outside what relation-oriented composition expresses
too. (`ho_count()` counts the extension of one predicate, which is a different
question.)

You can get close by counting the aggregated list in Python:

```python
authors = Author()
authors.rfk_posts.set()
for row in authors.ho_select(json_agg={'rfk_posts': ['id']}):
    post_count = len(row['rfk_posts'])
```

That works, and it is the wrong tool for the job. It ships every post id across
the wire to compute a number the database could have returned by itself, and the
count exists only once the rows arrive, so it cannot narrow the query: there is
no way to ask for authors with more than ten posts and have the database do the
filtering. The recommended answer is a view:

```sql
CREATE VIEW blog.author_post_count AS
  SELECT a.*, count(p.id) AS post_count
  FROM author a
  LEFT JOIN post p ON p.author_id = a.id
  GROUP BY a.id;
```

and then use it like any other relation, because halfORM doesn't distinguish
tables from views:

```python
APC = blog.get_relation_class('blog.author_post_count')
APC(post_count=('>', 10)).ho_count()
```

Is that better or worse? Honestly: it depends on who you are.

The cost is real: you write and maintain a view, you need DDL rights or a DBA,
and a one-liner became a two-step. If you're a solo developer on a greenfield
project, Django's version is plainly more convenient.

The benefit is also real: the view is available to every client of that database,
not just your Python app; it's version-controlled alongside the schema; it's
readable by anyone who knows SQL; and the query planner sees it as SQL rather than
as generated ORM output. If three services query this database and two of them
aren't in Python, the view is the only version of this logic that all three can
share.

So it's a position, not an oversight: complex query logic belongs in the database,
expressed in the language designed for it. But you should know you're choosing it.

The same escape hatches exist for everything else: `model.execute_function()`
and `model.call_procedure()` for stored routines, `model.execute_query()` for
arbitrary parameterised SQL returning dicts.

## When not to use halfORM

Since this is the comparison post, the fit question belongs here.

**Don't use it if** you need to support more than one database engine. halfORM
is PostgreSQL-only, deliberately and irreversibly: views, native table
inheritance and advanced types are all what makes the rest work.

**Don't use it if** your project is code-first and you like it that way. If your
team's model is "the Python classes are the schema", halfORM inverts your entire
workflow and you will fight it every day.

**Don't use it if** you're in Django. Django's ORM is woven into forms, the admin,
auth, and the migration system. Swapping it out means giving up the parts of
Django people use Django for.

**Do consider it if** your team is comfortable with SQL, you treat PostgreSQL as
a first-class component rather than a generic storage backend, and you work
against schemas that exist independently of your application: because someone
else owns them, because several applications share them, or because they predate
your code.

That last case is the one halfORM was built for, and it's more common in
enterprise settings than the greenfield-project literature suggests.

---

*For a hands-on comparison of your own, [Learn halfORM in half an hour](../half-an-hour.md).*
