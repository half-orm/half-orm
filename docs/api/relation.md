# Relation

A `Relation` object is a **predicate** — it describes the logical condition
that rows must satisfy to belong to the relation. Its *extension* is the set
of rows currently satisfying that predicate in the database.

Instantiating with keyword arguments specialises the predicate. **No SQL is
executed** until you call an executor method.

```python
Author()                          # tautology — the whole table
Author(last_name='Martin')        # subset: "is an author named Martin"
Author(last_name='Martin', id=42) # at most one row
```

**Executors** (`ho_select`, `ho_insert`, `ho_update`, `ho_delete`, `ho_count`,
`ho_is_empty`) execute SQL immediately and return results.
**Introspection** methods (`ho_assert_is_singleton`, `ho_is_set`,
`ho_where_display`, `ho_mogrify`) inspect or assert on the predicate without
touching the database.

See [Learn halfORM in half an hour](../half-an-hour.md) for a full walkthrough.

---

## Executors

These methods execute SQL immediately and return results.

::: half_orm.relation.Relation.ho_insert
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_select
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

!!! note "json_agg: FK direction determines the return type"
    When using the `json_agg` parameter, the type of each aggregated value
    depends on the FK direction:

    | FK type | Condition | Return value |
    |---|---|---|
    | Reverse (one-to-many) | no UNIQUE/PK on FK columns | `list` of dicts (`[]` if empty) |
    | Reverse (one-to-one) | FK columns have UNIQUE or PK | `dict` or `None` |
    | Direct (many-to-one) | — | `dict` or `None` |

    ```python
    # Reverse FK, non-unique — author → posts (list)
    alice = Author(last_name='Martin')
    alice.post_rfk.set()               # join all posts
    for row in alice.ho_select(json_agg={'post_rfk': ['title']}):
        print(row['post_rfk'])     # [{'title': '...'}, ...]

    # Direct FK — post → author (dict)
    post = Post(title='Hello')
    post.author_fk.set()               # join all authors
    for row in post.ho_select(json_agg={'author_fk': ['last_name']}):
        print(row['author_fk'])    # {'last_name': 'Martin'}

    # Chained FK (A ← B → C) — aggregate the leaf relation's data
    # For each post, collect the persons who commented on it.
    # post ← comment → person  (comment is the junction)
    post = Post(title='Hello')
    comment = Comment()
    comment.author_fk.set()            # chain: comment → person
    post.comment_rfk.set(comment)
    for row in post.ho_select(json_agg={'comment_rfk': ['last_name']}):
        print(row['comment_rfk'])  # [{'last_name': '...'}, ...]
    ```

    *Changed in version 0.18.7* **(breaking)**.

::: half_orm.relation.Relation.ho_count
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_is_empty
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_update
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_delete
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Async executors

Async counterparts of every executor. Require an async connection opened
with `await model.aconnect()`. Return plain values (not generators) so the
cursor can be closed before returning to the caller.

```python
import asyncio
from half_orm.model import Model

async def main():
    blog = Model('blog')
    await blog.aconnect()
    Author = blog.get_relation_class('blog.author')
    Post = blog.get_relation_class('blog.post')

    alice = await Author(
        name='Alice', email='alice@example.com'
    ).ho_ainsert()

    posts = await Post(author_id=alice['id']).ho_aselect()
    n     = await Post().ho_acount()

    await blog.adisconnect()

asyncio.run(main())
```

::: half_orm.relation.Relation.ho_ainsert
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

*Sync counterpart: [ho_insert](#half_orm.relation.Relation.ho_insert)*

::: half_orm.relation.Relation.ho_aselect
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

*Sync counterpart: [ho_select](#half_orm.relation.Relation.ho_select)*

::: half_orm.relation.Relation.ho_acount
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

*Sync counterpart: [ho_count](#half_orm.relation.Relation.ho_count)*

::: half_orm.relation.Relation.ho_ais_empty
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

*Sync counterpart: [ho_is_empty](#half_orm.relation.Relation.ho_is_empty)*

::: half_orm.relation.Relation.ho_aupdate
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

*Sync counterpart: [ho_update](#half_orm.relation.Relation.ho_update)*

::: half_orm.relation.Relation.ho_adelete
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

*Sync counterpart: [ho_delete](#half_orm.relation.Relation.ho_delete)*

---

## Bulk load

::: half_orm.relation.Relation.ho_copy
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_acopy
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

*Sync counterpart: [ho_copy](#half_orm.relation.Relation.ho_copy)*

---

## Introspection

These methods inspect or assert on the predicate **without executing SQL**.

::: half_orm.relation.Relation.ho_assert_is_singleton
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_is_set
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

!!! warning "Syntactic check, not semantic — risk of data loss"
    `ho_is_set()` inspects the predicate structure only. When both operands
    of a set operator are constrained, it returns `True` even if the
    extension is semantically equivalent to the full table:

    ```python
    Post() & Post()                             # False — both operands unconstrained
    Post() | Post(title='a')                    # True  — right operand is constrained
    Post(title='a') | Post(title=('!=', 'a'))   # True  — but = all posts
    ```

    Because `ho_delete()` and `ho_update()` allow execution without
    `delete_all=True` / `update_all=True` when `ho_is_set()` is `True`,
    these predicates will silently operate on the **entire table**.

    ```python
    # Deletes ALL posts — no error raised
    (Post(title='a') | Post(title=('!=', 'a'))).ho_delete()
    ```

    Always verify the actual extension with `ho_count()` or `ho_mogrify()`
    before destructive operations on set-operator predicates.

::: half_orm.relation.Relation.ho_where_display
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_mogrify
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_dict
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.Relation.ho_description
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

---

## Decorators

::: half_orm.relation.singleton
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: half_orm.relation.transaction
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

See also: [Transaction](transaction.md) — the context manager equivalent.