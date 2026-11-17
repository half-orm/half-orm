# half-orm 2.0.0 — Breaking Changes

## A Model refuses a database whose derived names collide

`Model(...)` and `reconnect(reload=True)` now raise `NamingError` when two
things end up under one Python name. Before, one of them was silently
dropped, so an application may have been running on such a database without
knowing it. The error lists every problem.

The usual case is two foreign keys that spell the same reverse name:

```sql
create table post (id int primary key, author_id int references author);
create table post_author (pk int primary key, id int references author);
-- both: _reverse_fkey_<db>_public_post_author_id
```

Also refused: a column named like a foreign-key attribute (`fk_owner` next
to a constraint `owner`), a column named like something `Relation` uses
(`ho_*`, `_ho_*`, `Fkeys`), a column that cannot be an attribute and is
exposed as `column<N>` next to a real `column<N>`, and two relations that
read the same without quotes (`"a.b".c` and `a."b.c"`).

**To settle one**, give one side a name of its own.

In the database:
```sql
COMMENT ON CONSTRAINT post_author_id_fkey ON post IS '@ho_reverse_name posts';
COMMENT ON COLUMN orders.fk_owner IS '@ho_name owner_ref';
```

Or on the Model, when the database cannot be written to:
```python
Model('legacy',
      reverse_names={('public.post', 'post_author_id_fkey'): 'posts'},
      field_names={'public.orders': {'fk_owner': 'owner_ref'}},
      ignore=['old.*'])       # or leave relations out altogether
```

A reverse key named this way is `_reverse_fkey_posts` in `Fkeys` and
`rfk_posts` on the relation. Renaming the constraint, the column or the
table settles it too.

**To find out before upgrading**, open the Model with 2.0.0 in a shell:
`python -m half_orm <config>` prints the list.

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
