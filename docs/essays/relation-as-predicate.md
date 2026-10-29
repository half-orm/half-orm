# A Relation Is a Predicate, Not an Object

Part 2 of six in *Relation-Oriented Programming*. [Series index](index.md)

The examples use the four-table blog schema of the
[running example](index.md#the-running-example): `author`, `post`,
`comment`, `comment_type`.

[Last time](vietnam-twenty-years-on.md) I argued that the structural problems of
ORM come from a design direction, and that inverting the direction dissolves
them. This one is about the object you get at the other end of that inversion,
because almost everything else follows from it.

Here is the whole idea in one line:

```python
Author(name='Alice')
```

This does not fetch Alice. It does not talk to the database at all. It is the
*set of authors whose name is Alice*: a description, not a result. In relational
algebra terms, `T(c1=v1, c2=v2)` denotes:

> σ<sub>c1 = v1 ∧ c2 = v2</sub>(T)

A selection. A predicate over a set of tuples. Nothing is materialised, nothing is
loaded, no connection is used, and the object you hold carries filter criteria
rather than row data.

Everything below is a consequence.

## Consequence 1: no identity, therefore no session

A classical ORM hands you a proxy for one row and then has to answer an
unanswerable question: when do two proxies denote the same row? That question is
where identity maps, sessions, detached-instance errors and expired-attribute
surprises all come from.

halfORM never constructs a proxy for a single entity, so the question never comes
up.

```python
# No entity loaded, no identity to track: direct update by predicate
Author(id=42).ho_update(name='Jane Doe')
```

There is no session to open, no unit of work to flush, no object to attach or
detach. An `UPDATE ... WHERE id = 42` is issued and that's the end of it.

The commitment goes all the way down to equality. `a == b` on two `Relation`
objects is defined as *the symmetric difference is empty*:

> a == b ⟺ (a ∖ b) ∪ (b ∖ a) = ∅

No primary keys involved, no memory addresses involved. Two predicates are equal
when they denote the same set of rows, which is a question about data, not about
memory. If both operands are literally the same Python object, the check
short-circuits and no query runs; otherwise it compiles to a single SQL query and
tests it for emptiness.

This sounds exotic until you notice that Python already does it: `{1,2,3} ==
{2,3,1}` is `True` because `set.__eq__` denotes extensional equality, not object
identity. Relations are sets. They get set equality.

Two honest qualifications. First, what's tested is *extensional* equality: given
the current database state, do these two predicates denote the same rows? That
is not logical equivalence (do they denote the same rows for *every* possible
state?), which would need a query-equivalence prover. Two predicates can agree
today and disagree tomorrow. Second, defining `__eq__` without `__hash__` makes
`Relation` instances unhashable in Python 3, so they can't be dict keys or set
members. That's deliberate: hashing a database-backed object by value would have
to issue a query, and hashing is supposed to be pure and cheap. The cost is
real; I'll come back to it under trade-offs.

## Consequence 2: dictionaries, not hydrated instances

`ho_select()` returns a generator of plain Python dictionaries, one per row.

```python
for row in Author(name=('ilike', 'a%')).ho_select():
    print(row['name'], row['email'])
```

No hydration. No deferred columns. No lazy attributes. You can project
explicitly with `ho_select('id', 'name')` if a wide table makes full fetches
expensive, but that's a performance choice, not a correctness one: there's no
object state to be partially populated, so partial loading has nothing to be
partial *about*.

The partial-object problem doesn't get solved. It stops being expressible.

## Consequence 3: set algebra, because sets have an algebra

Python's operators are overloaded on `Relation` objects, which means composition
is just arithmetic:

| Python | Relational algebra | SQL |
|---|---|---|
| <code>R &#124; S</code> | σ<sub>p1</sub>(T) ∪ σ<sub>p2</sub>(T) | `WHERE ... OR ...` |
| `R & S` | σ<sub>p1</sub>(T) ∩ σ<sub>p2</sub>(T) | `WHERE ... AND ...` |
| `R - S` | σ<sub>p1</sub>(T) ∖ σ<sub>p2</sub>(T) | `WHERE ... AND NOT (...)` |
| `R ^ S` | σ<sub>p1</sub>(T) △ σ<sub>p2</sub>(T) | symmetric difference |
| `R.fk(p)` | σ<sub>p1</sub>(T) ⋈<sub>FK</sub> σ<sub>p</sub>(U) | `JOIN U ON ...` |
| `R.ho_select(a1, …)` | π<sub>a1,…</sub>(σ<sub>p1</sub>(T)) | `SELECT a1, ...` |

In practice:

```python
published   = Post(published=True)
alice_posts = Author(name='Alice').rfk_posts()
bob_posts   = Author(name='Bob').rfk_posts()

all_theirs           = alice_posts | bob_posts     # union
all_theirs_published = published & all_theirs      # intersection
silent               = Author() - Post().fk_author()  # authors who never posted
```

Every one of those lines is a value. Not a query: a value. No SQL has been sent.
`silent` is a `Relation` you can pass to a function, store in a dict of named
filters, or compose further, and it will not touch the database until someone
calls a terminal method on it.

These algebraic properties aren't aspirational, either. halfORM ships a [test
suite](https://github.com/half-orm/half-orm/blob/main/test/relation/algebra_test.py)
that verifies the Boolean algebra laws (commutativity, associativity,
distributivity, De Morgan, double complement, the relative-complement
identities) and the classical relational identities, notably selection
push-through join, σ<sub>p</sub>(R) ⋈ S = σ<sub>p</sub>(R ⋈ S) when p mentions
only attributes of R. All of it against a live PostgreSQL instance. The laws are
theorems; the suite tests that halfORM's compilation preserves them end to end.

## Consequence 4: deferred execution, with a short list of terminals

Database interaction happens at a short list of method names, and they're
named after the SQL verbs rather than after a persistence vocabulary:

`ho_select`, `ho_get`, `ho_count`, `ho_insert`, `ho_update`, `ho_delete`,
`ho_is_empty`, plus `ho_copy` for bulk loading through `COPY FROM` and an
`ho_a*` counterpart to each of them for asyncio.

No `save()`, no `flush()`, no `merge()`, no `persist()`. The `ho_` prefix exists
for exactly one reason: to stay out of the way of the method names you want to
use for your own business logic.

`ho_select()` returns a generator and issues its SQL lazily, on first iteration.
The others execute immediately. And because a `Relation` *is* a set, iterating it
directly does what you'd expect:

```python
if author_filter:
    candidates = Author(name=('ilike', author_filter)).rfk_posts(published=True)
else:
    candidates = Post(published=True)

for row in candidates.ho_select(order_by='title', limit=20):
    process(row)
```

Ordering and pagination are arguments to the terminal method (the natural
execution point) rather than mutations of the predicate. The `Relation` itself
stays a pure description.

Comparison operators come from PostgreSQL, not from a DSL. A constructor
argument of the form `field=(comp, value)` generates `WHERE field comp value`
directly: `('>', 100)`, `('ilike', 'a%')`, `('in', [1, 2, 3])`. There is no
`__gte` suffix convention to learn, because there is no query language to learn
apart from SQL. When you exceed what the API expresses,
`model.execute_query(sql, values)` runs arbitrary parameterised SQL through
psycopg3 and hands you back dictionaries.

## Consequence 5: singletons are a structural property

Sometimes you really do mean one row. halfORM lets you say so, and checks it
*without querying*:

```python
# email is UNIQUE NOT NULL, so this predicate denotes at most one tuple. By definition.
Author(email='alice@example.com').ho_assert_is_singleton().ho_update(email='alice@example.org')

# name is not a key: raises NotASingletonError immediately, no round-trip
Author(name='Alice').ho_assert_is_singleton()
```

A predicate is a singleton when it constrains all the columns of the primary
key, or all the columns of a unique not-null key, to specific values. That's a
fact about the predicate and the schema; it needs no database access to
establish. FK navigation inherits it: if the join fixes the target's primary
key, the result is a singleton too.

For a method whose contract requires a singleton regardless of call site, there's
a decorator:

```python
class Author(...):
    @singleton
    def update_email(self, email):
        return self.ho_update(email=email)
```

And when you want the runtime guarantee rather than the structural one, `ho_get()`
issues the query and raises `NotFoundError` or `MultipleRowsError`.
`ho_assert_is_singleton()` says the predicate *could* match at most one row;
`ho_get()` says it *does* match exactly one.

## Consequence 6: transactions are explicit, because there's nothing ambient

No session means no ambient transaction to silently enrol things into. The psycopg3
connection runs in autocommit, so each terminal method is its own transaction. When
several must succeed or fail together, you say so:

```python
from half_orm.relation import transaction

class Author(db.get_relation_class('blog.author')):
    @transaction
    def create_with_posts(self, posts_data):
        author = self.ho_insert()
        for post_data in posts_data:
            Post(author_id=author['id'], **post_data).ho_insert()
        return author
```

A per-model nesting counter handles composition: level 0→1 disables autocommit and
opens a transaction; level n→n+1 creates a `SAVEPOINT`; coming back down releases
the savepoint or rolls back to it; level 1→0 commits and restores autocommit. A
helper method that is itself decorated with `@transaction` participates in the
enclosing one through a savepoint, so it can fail and roll back partially without
aborting the outer operation.

The body of the method is ordinary predicate code. Transactionality is the
wrapper's concern.

One more stateless consequence, this one about destruction. `ho_delete()` and
`ho_update()` on an unconstrained predicate require `delete_all=True` /
`update_all=True`, because there is no session tracking your intent and no
confirmation dialog between you and the whole table.

## What this costs

I'd rather state these than have you find them.

**No cache.** Every terminal method issues a query. There is no first-level or
second-level cache, and there can't be one: a `Relation` is a predicate, not a
snapshot, and its extension is evaluated against the current database state each
time. Caching is an application concern.

**PostgreSQL only.** The whole design rests on introspecting a live catalog with
a specific feature set: views, native table inheritance, advanced types. A
multi-DBMS abstraction would force exactly the lowest-common-denominator trades
that conventional ORMs make. If you need database portability, this isn't your
library.

**`__eq__` is not free.** The set-equality semantics is coherent inside the
model and dangerous outside it. `x in [r1, r2, r3]` calls `list.__contains__`,
which calls `r1.__eq__(x)`, `r2.__eq__(x)`, each potentially a SQL round trip,
with nothing at the call site to warn you. For membership tests you control, use
`ho_list(*relations)`, which folds its operands under `|` into one union
predicate so that `x in ho_list(r1, r2, r3)` dispatches to
`Relation.__contains__` and runs a single query. The residual risk (handing
`Relation` objects to an external framework that calls `__eq__` internally for
caching or deduplication) is irreducible. Don't put them in generic containers.

**Type safety.** `ho_select()` is typed `Iterator[dict[str, Any]]`, so your IDE
can't complete column names and mypy can't catch `row['naem']`. That's a real
cost of returning dictionaries, and it has an answer: generated `TypedDict`s and
base classes derived from the live schema, with no schema declaration written by
hand. half-orm-dev generates both from the same introspection, alongside the
model itself.

**Set semantics vs SQL multisets.** SQL works on multisets; joins can produce
duplicates that the relational model wouldn't. `ho_select` removes duplicate
primary keys automatically and warns you to pass `distinct=True` so the database
does it instead. More on this next time, where the joins come in.

## The shape of the thing

Step back and the pattern is uniform: each design decision refuses to introduce
into the model any state or abstraction that has no counterpart in the relational
model itself. No identity, because sets don't have identity. No hydrated state,
because tuples aren't objects. No ambient transaction, because there's no session
to host one. No proprietary query language, because SQL already exists.

What's left is small, and it composes. Part 3 is about the operation that makes
it worth using: what happens when you follow a foreign key.

---

*The predicate model is specified in [Fundamentals](../fundamentals.md) and the full API in [Relation](../api/relation.md).*
