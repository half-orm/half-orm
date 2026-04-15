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