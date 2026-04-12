# Field

A `Field` attribute represents a single column on a relation. halfORM exposes
all columns automatically as `Field` instances on every relation object.

Two usage patterns:

* **Read** — inspect the current constraint value or schema metadata:
  `field.value`, `field.name`, `field.py_type`, `field.is_set()`,
  `field.is_not_null()`.
* **Write** — constrain the field to filter rows:
  `field.set(value)`, `field.set((comp, value))`.

Constraints are usually set via keyword arguments when instantiating a
relation, but `.set()` is useful when you need a non-`=` comparator,
`unaccent`, a column-to-column comparison, or an arithmetic expression:

```python
author = Author()
author.last_name.set(('ilike', 'mar%'), unaccent=True)

post = Post()
post.views.set(('>', post.likes))                       # WHERE views > likes
post.views.set(('>=', Expr('2 * "likes"')))             # WHERE views >= 2 * likes
```

Setting any field to `None` removes that constraint.

See [Learn halfORM in half an hour](../half-an-hour.md#3-filtering-select-2-min)
for a full walkthrough of filtering and comparators.

---

## SQL expressions

::: half_orm.field.Expr
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Constraint

::: half_orm.field.Field.set
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Inspection

::: half_orm.field.Field.is_set
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.field.Field.value
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.field.Field.name
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.field.Field.py_type
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.field.Field.is_not_null
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.field.Field.unaccent
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3