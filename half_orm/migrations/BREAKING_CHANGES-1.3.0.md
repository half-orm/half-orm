# half-orm 1.3.0 — Breaking Changes

## A relation is no longer a mapping

`Relation.keys()`, `Relation.items()` and `rel['col']` are removed, and with
them `Other(**rel)`. `dict(rel)` no longer means anything either — and does
not necessarily fail: a relation is still iterable, over its rows, so the
call now runs the query and tries to build a dict out of them.

They returned the *predicate* — the constraint set on each column, `None`
for the columns left unconstrained — not a row. Rows are the `dict`s that
`ho_get()` and `ho_select()` return, and those are unchanged.

**Before:**
```python
person = Person(last_name='Lagaffe')

person['last_name']        # 'Lagaffe'
list(person.keys())        # every column name
dict(person)               # {'id': None, 'first_name': None, 'last_name': 'Lagaffe', ...}
Other(**person)
```

**After:**
```python
person = Person(last_name='Lagaffe')

person.last_name.value     # 'Lagaffe'
list(person._ho_fields)    # every column name
person.ho_dict()           # {'last_name': 'Lagaffe'} -- only what is set
Other(**person.ho_dict())
```

`ho_dict()` leaves out the columns that carry no constraint, where
`dict(rel)` listed them with `None`. Passed back to a constructor the two
are equivalent, `None` meaning "no constraint" there.

The idiom most likely to be affected rebuilt a relation from a row and then
read it like one:

```python
aa = Person(**Person(last_name='aa').ho_get())
aa['id']                   # before
aa.id.value                # after -- or keep the row: Person(...).ho_get()['id']
```

A column named `keys` or `items` is now an ordinary column.
