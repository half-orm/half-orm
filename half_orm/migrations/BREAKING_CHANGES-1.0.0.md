# half-orm 1.0.0 — Breaking Changes

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