# half-orm 1.0.0 — Breaking Changes

## Legacy unprefixed API removed

The method names without the `ho_` prefix, deprecated since 0.x, no longer
exist: `select`, `insert`, `update`, `delete`, `get`, `count`, `is_empty`,
`unaccent`, `order_by`, `limit`, `offset`, `_mogrify`.

**Before:**
```python
for row in Author(last_name='Martin').select('id'):
    ...
Author(id=1).update(email='a@example.com')
```

**After:**
```python
for row in Author(last_name='Martin').ho_select('id'):
    ...
Author(id=1).ho_update(email='a@example.com')
```

`order_by`, `limit` and `offset` are keyword arguments of `ho_select()`, see
below.

## `DC_Relation` removed from `half_orm.relation`

This IDE type-checking stub is no longer shipped with the library. It is
generated for each project by `half-orm-dev`, in the package's
`ho_baseclasses.py`.

## `ho_get()` returns a `dict` and raises on 0 or >1 rows

`ho_get()` now returns a plain `dict` directly (no longer a Relation
object).  It raises:
- `NotFoundError` if no row matches
- `MultipleRowsError` if more than one row matches

**Before:**
```python
obj = MyTable(id=1).ho_get()  # returned a Relation
```

**After:**
```python
row = MyTable(id=1).ho_get()  # returns dict, or raises
```

The async counterpart `ho_aget()` has been added with the same semantics.

## Deprecated query-builder setters removed

`ho_limit`, `ho_offset`, `ho_order_by`, `ho_distinct` no longer exist as
property setters.  Pass them as keyword arguments to `ho_select()`.

**Before:**
```python
rel.ho_limit = 10
rel.ho_order_by = "name"
for row in rel.ho_select():
    ...
```

**After:**
```python
for row in rel.ho_select(limit=10, order_by="name"):
    ...
```

## `FKEYS_PROPERTIES` / `FKEYS` class attributes removed

Use `Fkeys` only.  Any subclass that still defines `FKEYS_PROPERTIES` or
`FKEYS` will raise an error at class definition time.

## `ho_cast()` raises `CastError` for invalid inheritance targets

`ho_cast(TargetClass)` now raises `half_orm.relation_errors.CastError` if
`TargetClass` is not in the PostgreSQL inheritance hierarchy of the
source table.