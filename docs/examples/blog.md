# Simple Blog

A complete, runnable example: a small blog with authors, posts and typed
comments (comments / reviews / questions). The schema and the data below are
not invented for this page — they are the exact fixtures used by the
`blog_demo` end-to-end demo in [half-orm-gen](https://github.com/half-orm/half-orm-gen),
where the same tables are turned into a REST API and an admin UI with a single
command. Here we use them to walk through halfORM itself.

## What This Example Demonstrates

- A small but realistic **multi-schema** design (`actor` for identity, `blog`
  for content)
- A **lookup table** (`comment_type`) instead of a `CHECK` constraint or enum
- **FK navigation** in both directions (post → author, author → posts)
- **Predicate algebra** to answer "posts with at least one review" style questions
- **`json_agg`** to fetch a post with its comments in one query
- A **transactional** custom method (`publish`) that inserts a post and its
  opening comment atomically

## Schema

```sql
CREATE SCHEMA actor;
CREATE SCHEMA blog;

CREATE TABLE actor."user" (
    id    uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    name  text NOT NULL,
    email text NOT NULL UNIQUE
);

CREATE TABLE blog.comment_type (
    name text NOT NULL PRIMARY KEY
);

CREATE TABLE blog.post (
    id        uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    title     text NOT NULL,
    content   text,
    published boolean NOT NULL DEFAULT false,
    author_id uuid REFERENCES actor."user"(id) ON DELETE CASCADE
);

CREATE TABLE blog.comment (
    id           uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    content      text NOT NULL,
    post_id      uuid REFERENCES blog.post(id) ON DELETE CASCADE,
    author_id    uuid REFERENCES actor."user"(id) ON DELETE CASCADE,
    comment_type text REFERENCES blog.comment_type(name)
);
```

!!! note "Why a lookup table for `comment_type`?"
    `comment`, `review` and `question` could have been a `CHECK` constraint or
    a Python `Enum`. A table means new types can be added with an `INSERT`,
    no migration required — and it gives the column a real foreign key that
    halfORM can navigate, like any other relationship.

## Sample data

```sql
INSERT INTO blog.comment_type (name) VALUES
    ('comment'), ('review'), ('question');

INSERT INTO actor."user" (id, name, email) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'Alice Martin',  'alice@half-orm.org'),
    ('a1000000-0000-0000-0000-000000000002', 'Bob Dupont',    'bob@half-orm.org'),
    ('a1000000-0000-0000-0000-000000000003', 'Clara Nguyen',  'clara@half-orm.org'),
    ('a1000000-0000-0000-0000-000000000004', 'David Leclerc', 'david@half-orm.org'),
    ('a1000000-0000-0000-0000-000000000005', 'Eva Rossi',     'eva@half-orm.org');

INSERT INTO blog.post (id, title, content, published, author_id) VALUES
    ('b2000000-0000-0000-0000-000000000001',
     'Introduction à halfORM',
     'halfORM est un ORM Python minimaliste basé sur PostgreSQL. Il repose sur une approche sans migration : le modèle relationnel est la source de vérité.',
     TRUE, 'a1000000-0000-0000-0000-000000000001'),

    ('b2000000-0000-0000-0000-000000000007',
     'Générer une API REST depuis un schéma SQL',
     'CRUD_ACCESS et halfORM-litestar permettent de déclarer les droits d''accès directement dans le modèle Python, sans écrire de routes à la main.',
     TRUE, 'a1000000-0000-0000-0000-000000000002'),

    ('b2000000-0000-0000-0000-000000000008',
     'Tailwind CSS 4 : ce qui arrive',
     'La configuration passe en CSS natif, les utilitaires sont générés à la demande.',
     FALSE, 'a1000000-0000-0000-0000-000000000003');

INSERT INTO blog.comment (id, content, post_id, author_id, comment_type) VALUES
    ('c3000000-0000-0000-0000-000000000001',
     'Très bon article, j''utilise halfORM depuis 6 mois et la courbe d''apprentissage est douce.',
     'b2000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000002', 'comment'),

    ('c3000000-0000-0000-0000-000000000002',
     '★★★★★ — Exactement ce que je cherchais pour remplacer SQLAlchemy dans mes projets async. Migré en un week-end.',
     'b2000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000003', 'review'),

    ('c3000000-0000-0000-0000-000000000003',
     'Est-ce que halfORM supporte les schémas multiples dans la même base ?',
     'b2000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000004', 'question'),

    ('c3000000-0000-0000-0000-000000000016',
     '★★★★★ — J''ai généré une API complète en 20 minutes. Bluffant.',
     'b2000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000003', 'review');
```

!!! tip "Full fixtures"
    This is a trimmed excerpt (3 posts, 4 comments) for readability. The
    complete set — 5 authors, 10 posts, 20 comments (7 reviews) — lives at
    [`fixtures/blog_demo_data.sql`](https://github.com/half-orm/half-orm-gen/blob/main/fixtures/blog_demo_data.sql)
    in half-orm-gen and is what the running demo actually loads.

## Connect and explore

```python
from half_orm.model import Model

blog = Model('blog_demo')
print(blog)
```

```
📋 Available relations for blog_demo:
r "actor"."user"
r "blog"."comment"
r "blog"."comment_type"
r "blog"."post"
```

```python
User        = blog.get_relation_class('actor.user')
Post        = blog.get_relation_class('blog.post')
Comment     = blog.get_relation_class('blog.comment')
CommentType = blog.get_relation_class('blog.comment_type')

print(Post())
```

```
SCHEMA: blog
TABLE: post

FIELDS:
- id:        (uuid) NOT NULL
- title:     (text) NOT NULL
- content:   (text)
- published: (bool) NOT NULL
- author_id: (uuid)

PRIMARY KEY (id)
FOREIGN KEYS:
- _reverse_fkey_blog_demo_blog_comment_post_id: ("id")
 ↳ "blog_demo":"blog"."comment"(post_id)
- post_author_id_fkey: ("author_id")
 ↳ "blog_demo":"actor"."user"(id)
```

## Naming the foreign keys

`print()` gives the real, introspected FK names — verbose, but exact. Subclass
each relation, register it, and give the FKs short aliases:

```python
from half_orm.model import register

@register
class User(blog.get_relation_class('actor.user')):
    Fkeys = {
        'comment_rfk': '_reverse_fkey_blog_demo_blog_comment_author_id',
        'post_rfk':    '_reverse_fkey_blog_demo_blog_post_author_id',
    }

@register
class Post(blog.get_relation_class('blog.post')):
    Fkeys = {
        'comment_rfk': '_reverse_fkey_blog_demo_blog_comment_post_id',
        'author_fk':   'post_author_id_fkey',
    }

@register
class Comment(blog.get_relation_class('blog.comment')):
    Fkeys = {
        'post_fk':         'comment_post_id_fkey',
        'author_fk':       'comment_author_id_fkey',
        'comment_type_fk': 'comment_comment_type_fkey',
    }

@register
class CommentType(blog.get_relation_class('blog.comment_type')):
    Fkeys = {
        'comment_rfk': '_reverse_fkey_blog_demo_blog_comment_comment_type',
    }
```

`_reverse_fkey_blog_demo_...` names are qualified with the database name
(`blog_demo`) because halfORM derives them from PostgreSQL's own catalog,
which has no notion of your Python aliases — see
[Foreign keys](../half-an-hour.md#8-foreign-keys-composing-predicates-across-tables-10-min)
for the naming rule.

## Queries

Published posts, ordered by title:

```python
for row in Post(published=True).ho_select('title', order_by='title'):
    print(row['title'])
```

Reviews left on a given post, via FK navigation:

```python
intro = Post(id='b2000000-0000-0000-0000-000000000001')
for row in intro.comment_rfk(comment_type='review').ho_select('content'):
    print(row['content'])
```

Every post written by Bob, going the other way (author → posts):

```python
bob = User(email='bob@half-orm.org')
for row in bob.post_rfk.ho_select('title'):
    print(row['title'])
```

A post together with all its comments, in a single query:

```python
intro = Post(id='b2000000-0000-0000-0000-000000000001')
intro.comment_rfk.set()

for row in intro.ho_select(json_agg={'comment_rfk': ['content', 'comment_type']}):
    print(row['title'])
    for comment in row['comment_rfk']:
        print(' -', comment['comment_type'], ':', comment['content'])
```

### Predicate algebra: posts with no reviews yet

```python
reviewed = Post().comment_rfk.set(comment_type='review')
unreviewed = Post(published=True) - reviewed

for row in unreviewed.ho_select('title'):
    print(row['title'])
```

`reviewed` is "published or not, has at least one review". Subtracting it from
"published posts" is plain set difference — no SQL `NOT EXISTS` to write by
hand.

## Insert: publish a post and its first comment atomically

```python
from half_orm.relation import singleton, transaction

@register
class User(blog.get_relation_class('actor.user')):
    Fkeys = {
        'comment_rfk': '_reverse_fkey_blog_demo_blog_comment_author_id',
        'post_rfk':    '_reverse_fkey_blog_demo_blog_post_author_id',
    }

    @singleton
    @transaction
    def publish(self, title: str, content: str):
        """Insert a post and seed it with an opening comment, atomically."""
        post = self.post_rfk(title=title, content=content, published=True).ho_insert()
        self.comment_rfk(
            post_id=post['id'], content='First!', comment_type='comment',
        ).ho_insert()
        return post

alice = User(email='alice@half-orm.org')
alice.publish('UUID v7 in practice', 'A follow-up to the UUID v4 vs v7 post...')
```

`self.post_rfk(...)` and `self.comment_rfk(...)` both navigate from a
singleton (`alice`), so `author_id` is already bound to Alice's `id` — only
`title`/`content` and `post_id`/`content`/`comment_type` need to be supplied.
If the comment insert fails, the post insert rolls back too: `publish` either
fully succeeds or leaves no trace.

## Next steps

This same schema and data are what
[`half-orm-gen`](https://github.com/half-orm/half-orm-gen) uses in its
`blog_demo` end-to-end demo: run `half_orm gen api --litestar` and
`half_orm gen frontend --svelte` against it and you get a working REST API
and admin UI for these exact tables — `published`, `comment_type` and the
author FK already wired up, no extra configuration needed to follow along.

* [Database Exploration with GitLab](gitlab.md)
* [Instant REST API with halfORM](instant-rest-api/instant-rest-api.md)
