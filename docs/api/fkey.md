# FKey

A `FKey` attribute represents a foreign key (or reverse foreign key) on a
relation. halfORM exposes all FKs automatically; give them friendly names
via the `Fkeys` class attribute and use them to navigate between tables or
compose JOIN conditions.

Two usage patterns:

* **Call** the attribute — `post.author_fk()` — to navigate: returns the
  related relation restricted to rows linked to the current predicate.
* **`.set(rel)`** — adds a JOIN condition on the owning relation. Called
  with no argument, `.set()` joins against all rows of the related table
  (equivalent to `.set(RelatedClass())`).

Print any relation instance to discover FK names (internal names to copy
into `Fkeys`).

See [Learn halfORM in half an hour](../half-an-hour.md#8-foreign-keys-composing-predicates-across-tables)
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