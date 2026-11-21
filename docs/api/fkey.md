# FKey

A `FKey` attribute represents a foreign key (or reverse foreign key) on a
relation. halfORM exposes all FKs automatically; give them friendly names
via the `Fkeys` class attribute and use them to navigate between tables or
compose JOIN conditions.

Two usage patterns:

* **Call** the attribute — `post.author_fk()` — to navigate: returns the
  related relation restricted to rows linked to the current predicate.
* **`.set(...)`** — adds a JOIN condition on the owning relation. Three
  forms, all without importing the related class:
    - `.set()` — join all rows (tautological predicate).
    - `.set(field=value, ...)` — join with constraints.
    - `.set(rel)` — join against an existing `Relation` instance.

Print any relation instance to discover FK names (internal names to copy
into `Fkeys`).

A direct FK carries the constraint name PostgreSQL gave it. A reverse FK has
no constraint of its own, so halfORM builds one from the referencing side:

```
_reverse_fkey_<database>_<schema>_<table>_<field>
```

The database name is part of it. When a database and one of its schemas share
a name, a common enough arrangement, the word appears twice, as in
`_reverse_fkey_blog_blog_post_author_id`. It reads like a typo and is not one;
a name missing that component matches no foreign key. Copy the names from the
printed relation rather than assembling them by hand.

Joining the parts with underscores lets two different foreign keys spell the
same: `post(author_id)` and `post_author(id)` both give
`_reverse_fkey_blog_blog_post_author_id`. halfORM does not pick one:
`Model()` raises a `NamingError` listing every such collision. It is settled
by giving one of the two reverse keys a name of its own, which replaces the
convention: the key is then `_reverse_fkey_<name>`.

- In the database, where every client reads it, with an annotation line in
  the constraint's comment (the rest of the comment is free text):

  ```sql
  COMMENT ON CONSTRAINT post_author_id_fkey ON blog.post
      IS '@ho_reverse_name posts';
  ```

- On the Model, for a database you cannot write to (this declaration wins
  over the one in the database):

  ```python
  blog = Model('blog',
               reverse_names={('blog.post', 'post_author_id_fkey'): 'posts'})
  ```

Either way the reverse key becomes `_reverse_fkey_posts`, exposed by default
as `rfk_posts`.

The name is declared on the constraint, in the referencing table, although it
appears on the referenced one. The constraint is the only object that carries
the link: its comment goes away with it when it is dropped and stays with it
when it is renamed, and the change that adds a foreign key can name its
reverse in the same place.

A declared name *replaces* the derived one; it is not an alias. Naming a
reverse key is a rename, like renaming a column, and code written against the
derived name stops working:

- `author.rfk_blog_blog_post_author_id` raises `AttributeError`;
- an `Fkeys` entry whose value is `'_reverse_fkey_blog_blog_post_author_id'`
  raises `WrongFkeyError` when the class is instantiated, and the message
  gives the name that replaced it.

Declare the name before writing code against the key, or update the `Fkeys`
that use it in the same change. In a collision, the other foreign key keeps
the derived name: an `Fkeys` entry using that name still works, but leads to
that other key, so check it was the one meant.

---

## Fkeys on views

PostgreSQL stores no FK metadata for views, so halfORM cannot discover
navigation attributes automatically. Use a **dict** as the `Fkeys` value
instead of the internal FK name string:

```python
class PostComment(blog.get_relation_class('blog.view.post_comment')):
    Fkeys = {
        # direct FK: view.author_id → blog.author.id
        'fk_author': {
            'to':   'blog.author',
            'join': [('author_id',), ('id',)],
        },
        # reverse FK: blog.comment.post_id → view.id
        'rfk_comments': {
            'to':   'blog.comment',
            'join': [('id',), ('post_id',)],
        },
        # composite FK (two columns)
        'fk_address': {
            'to':   'geo.address',
            'join': [('country_code', 'city_code'), ('country', 'city')],
        },
    }
```

| Field | Type | Description |
|-------|------|-------------|
| key | `str` | Attribute name. **Must** start with `fk_` (direct) or `rfk_` (reverse). |
| `to` | `str` | Target relation as `'schema.table'`. |
| `join` | `list` | `[(source_cols,), (target_cols,)]` — view columns first, target columns second. |

Source columns are validated against the view's fields at instantiation; a
`ValueError` is raised immediately if a column is missing or the key prefix
is absent.

!!! note "Tables use a different format"
    For tables, `Fkeys` values are strings (internal FK names shown by
    `print(Post())`). The dict format is only needed for views and
    materialised views.

See [Learn halfORM in half an hour](../half-an-hour.md#8-foreign-keys-composing-predicates-across-tables-10-min)
for a full walkthrough.

---

## Navigation

::: half_orm.fkey.FKey.__call__
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Join condition

::: half_orm.fkey.FKey.set
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3