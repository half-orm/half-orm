# The Vietnam of Computer Science, Twenty Years On

Part 1 of six in *Relation-Oriented Programming*. [Series index](index.md)

In June 2006, Ted Neward published an essay called *The Vietnam of Computer
Science*. Object-relational mapping, he argued, is a quagmire: easy early
victories, steady mission creep, mounting costs, and no clean exit. The analogy
was deliberately provocative and the essay became one of those things many
developers have heard of and fewer have read.

Twenty years later, the frameworks are all still here. Hibernate, SQLAlchemy,
Django ORM, ActiveRecord: none of them went away, and every one of them got
bigger. Each ships its own query language on top of SQL. Each requires you to
hold two models in your head at once: the object graph you wrote and the tables
underneath it. That's usually where the retrospective ends: *ORM is still a mess,
ha ha, anyway back to work.*

I want to make a sharper claim. The problems Neward catalogued are not a maturity
issue that twenty more years of engineering will fix. They are consequences of a
design decision that every mainstream ORM makes on its first page, and they
persist because that decision persists.

## The catalogue

Start with the problems themselves. The literature has converged on a stable
list (Ireland et al. gave the most systematic academic treatment in 2009) and
six of them show up at runtime, independently of how your schema changes over
time.

**Identity.** Your language says two things are the same when they're at the same
memory address. Your database says two rows are the same when their primary keys
match. An ORM has to decide when two in-memory objects denote the same tuple, and
there is no clean answer once objects can be partially loaded, cached, or detached
from a session. Hence identity maps. Hence `DetachedInstanceError`. Hence every
hour you have ever spent reasoning about what a session does.

**Partial object.** A tuple has a fixed set of columns. An object is expected to
carry complete state. So the ORM must choose: load everything eagerly, which is
wasteful, or defer column loads lazily, which is complex and surprising. Neither
is universally right, so every framework exposes knobs and every codebase gets
them wrong somewhere.

**Inheritance.** Class hierarchies have no relational equivalent.
Table-per-hierarchy, table-per-class, table-per-concrete-class: three strategies,
each trading away query complexity, normalisation, or type safety. You pick one
early, you live with it for years.

**Navigation, a.k.a. N+1.** Walking an association either issues one query per
object (the N+1 problem) or joins everything upfront whether you needed it or
not. Both extremes are wrong in general, so frameworks expose per-association
fetch strategies, and N+1 keeps showing up in production anyway because the fix
is opt-in at every call site.

**Encapsulation.** The framework has to reflectively read and write every
persistent field, which means your domain classes have to expose every persistent
field. Your object design is now partly dictated by your persistence layer.

**Query language.** SQL is the native language of the relational model, but an
object-centric ORM can't hand it to you directly without breaking its own
abstraction. So you get HQL, JPQL, the Django ORM API, LINQ, each a partial
reimplementation of a language that already existed and was already complete.
You learn a dialect with its own documentation, its own edge cases, and its own
version history, and at the end of it you cannot express anything you couldn't
have expressed in SQL.

Then there's a seventh problem that lives on a different axis entirely.

**Ownership.** Who is allowed to change the schema, and how does the change
reach the other side? In code-first ORMs the application claims authority: you
edit a class, a migration tool generates DDL, the database follows. That works
beautifully on a greenfield project and starts leaking the moment reality
intrudes: a second application sharing the schema, a DBA adding an index, a
schema that predates your code by a decade. Database-first tools invert the
authority but usually provide no mechanism to propagate a change back into
application code: rename a column and every query referencing it breaks, some of
them loudly, some of them silently.

And the real difficulty underneath ownership is atomicity. A migration that
renames a column must ship *simultaneously* with the code that uses the new name.
That is structurally hard when a code generator owns the generated files, because
regeneration overwrites whatever you wrote by hand.

## They aren't seven problems

These are not seven independent defects that happen to cluster in the same kind
of software.

Identity is underneath partial objects and encapsulation both: you only need to
track which object is which because objects hold state, and you only need
reflective field access because the framework has to put state into them and get
it back out. Lazy loading compounds navigation: N+1 exists because association
traversal is allowed to issue a query behind your back, and it's allowed to do
that because the framework is pretending an object graph is in memory when it
isn't. Query languages exist because exposing SQL would reveal that the object
facade is a facade. And ownership compounds all of it: a code-first migration tool
can't regenerate your model without risking your hand-written code.

Pull on any thread and you arrive at the same knot. Every mainstream ORM starts
from the commitment that **the relational model should be hidden from the
application developer**, and that **schema authority flows from application code
to the database**. Every one of the problems above is that commitment coming
due.

This is why twenty years of engineering effort hasn't dissolved them. The effort
was spent making the facade better. The facade is the problem.

## Direction, not quality

So the claim I want to make is narrow and, I think, falsifiable: the structural
ORM problems are a consequence of *design direction*, not of implementation
quality. Hibernate is not badly built. SQLAlchemy is a genuinely great piece of
software. They are excellent implementations of a direction that generates these
problems by construction.

Directions can be inverted.

Suppose you take the opposite commitment: **the live database schema is the sole
source of truth for the structure of your data access layer.** Not
"database-first" in the weak sense of designing the schema before the code, but
in the strong sense that no table, no column, no type, no key, no constraint is
ever declared in the host language, and the access layer reads all of it from
the live catalog at startup.

What happens to the seven problems?

Identity has no meaning, because there is no entity proxy to identify: you get
an object that denotes a *set* of rows, and a set has no identity to track.
Partial objects have no meaning, because query results are plain dictionaries
and nothing holds state between calls. Code-first inheritance has no meaning,
because mapping only ever runs schema-to-code. N+1 has no meaning, because
foreign-key navigation builds a join instead of issuing a query. Encapsulation
is unconstrained, because there are no persistent fields inside the object to
reflect on. And SQL remains the query language, because there is no facade left
to protect.

Note the shape of those sentences. Not "solved". Not "mitigated with a
well-chosen default". *Has no meaning.* The problems don't get fixed; the concepts
they presuppose stop existing.

That's not a resolution of the impedance mismatch. It's a dissolution.

## What this series is

[halfORM](https://github.com/half-orm/half-orm), a Python library for
PostgreSQL, is built on this principle. This series takes the argument apart into
pieces you can evaluate one at a time:

2. **A relation is a predicate, not an object**: the core abstraction, set
   algebra on Python objects, and what happens to `__eq__` when equality means
   set equality.
3. **You can't have an N+1 problem if navigation isn't a query**: foreign-key
   navigation as join construction, with zero configuration.
4. **Delete your repository layer**: why query logic can live on the relation
   class once there's no session, and what that does to code organisation.
5. **halfORM vs SQLAlchemy Core vs Django ORM**: three queries, side by side,
   including the one where halfORM loses.
6. **Git is the migration tool**: the ownership problem, and what schema
   co-evolution looks like when git is the authority rather than a migrations
   table.

One more thing about the name. halfORM covers exactly half of SQL: the data
manipulation half (`INSERT`, `SELECT`, `UPDATE`, `DELETE`). It has no opinion
whatsoever about `CREATE TABLE`. Schema definition belongs to the database and
to the people who administer it, expressed in the language designed for it.

I picked that name years before I read Neward's essay carefully enough to notice
what he says near the end: the traditional answers to the impedance mismatch
amount to *"effectively 'solving' the problem by ignoring one half of it."* He
meant it as a criticism. I'd argue it's the right move, as long as you're
deliberate about which half you're ignoring and who owns it instead.

---

*The design decisions this diagnosis leads to are catalogued in [Fundamentals](../fundamentals.md).*
