# Git Is the Migration Tool

Part 6 of six in *Relation-Oriented Programming*. [Series index](index.md)

The examples use the four-table blog schema of the
[running example](index.md#the-running-example): `author`, `post`,
`comment`, `comment_type`.

The first five essays in this series were about runtime: what a data access layer
looks like when the live schema is the sole source of truth. This one is about
time. Schemas change. Code that uses them has to change with them. That's the
*ownership problem*, and it's on a different axis from everything else: it isn't
dissolved by removing a concept, because there's no concept to remove. It has to
be dissolved by a workflow that makes the bad situation unreachable.

Three things go wrong.

**Ownership.** In code-first ORMs the application claims authority over the
schema: edit a class, generate a migration, the database follows. Fine until a
second application shares the schema, or a DBA adds an index, or the schema
predates your code by a decade. In database-first tools the database owns the
schema but nothing propagates changes back into application code: rename a
column and every query referencing it breaks, some loudly, some silently.

**Drift.** Any code generator that reads a schema will, on its next run, overwrite
whatever you wrote into the generated files. So either you never regenerate, and
your code drifts from the schema, or you regenerate and lose your work.

**Atomicity.** The migration that renames a column must deploy *simultaneously*
with the code that uses the new name. Not "shortly after". Simultaneously. Most
setups achieve this with deployment discipline and hope.

half-orm-dev drives all of this through `half_orm dev`, and is built on two
choices that together make all three unreachable: **SQL is the patch language**,
and **git is the versioning infrastructure**. Everything else follows.

## Choice 1: patches are SQL files

A patch is a directory of `.sql` and `.py` files, applied in lexicographic order.
`.sql` files do the DDL and in-place data transformations, and are typically
written by the DBA. `.py` files handle migrations that need to iterate over rows
or touch the Python model, and are written by the developer. A patch with no
schema change contains only `.py` files.

Not a Python function à la Alembic. Not a Java method à la Flyway. Not an XML
descriptor à la Liquibase.

The argument is the same one as for queries. The relational model already has a
complete, precise, standard language for describing schema changes. Layering a
Python or Java DSL on top adds an abstraction that can be *wrong* (the generated
SQL may not be what you meant), requires the migration framework to be installed
and understood to read your own history, and severs the connection between the
artefact you wrote and the statement that ran.

This trades away real things. Flyway, Liquibase and Alembic give you automatic
rollback generation, cross-DBMS portability, and structured validation pipelines
that plain SQL files don't provide. What you get in exchange is directness and
auditability: a patch file can be read in any editor, applied with `psql`, and
understood by anyone who knows SQL, which, for a schema change, is everyone who
should be reviewing it.

There is exactly one thing patches are not for, and it gets its own directory.
`bootstrap/` at the project root holds `.sql` and `.py` files that run in
alphabetic order, once, when a brand-new instance is created by
`half_orm dev clone`, immediately after the schema is restored. They never run
on `patch apply`, `patch merge`, `release promote` or `upgrade`: nothing resets
the database between those, so a script that is not independently idempotent
would corrupt it the second time through.

What belongs there is what is specific to *this* instance: the first admin
account, a per-site secret. What does not is reference data every instance
should carry. A new system role is a patch, written as idempotent DML like any
other; it reaches existing instances through `upgrade` and is captured in the
release's data snapshot, which `bootstrap/` scripts never are.

The distinction matters more than it looks. Anything shared travels the patch
path, which is versioned, reviewed and replayed identically everywhere.
`bootstrap/` is the deliberate exception for what cannot be shared, and keeping
it that narrow is what stops it becoming a second, unaudited migration
channel.

## Choice 2: the zone discipline

`half_orm dev patch apply` is the atomic unit of the whole workflow, and it
does not work incrementally. It restores the database from the production
baseline, replays every patch already staged for the release, applies the files
of the patch you are working on in order, then introspects the updated live
schema and regenerates the model classes. When it returns, the Python model
reflects the schema exactly, and it does so from a known starting point rather
than from whatever your local database had drifted into.

That rebuild is why the command can be run again and again while you write the
patch. Getting a statement wrong costs you nothing: fix the file, run it again,
and the database is rebuilt from the baseline with your correction in place.

That regeneration is exactly the destructive step described above. What makes it
safe is that every generated file is split by sentinel comments into two regions:

- The **generated zone** holds introspected columns, the primary key description,
  and the foreign-key graph. Overwritten unconditionally, every time.
- The **developer zone** holds `Fkeys` aliases, `@singleton` guards, and business
  methods. Never touched. Ever.

```python
from half_orm.model import register
from blog import MODEL, ho_baseclasses

#>>> PLACE YOUR CODE BELOW THIS LINE.       # developer zone (module level)
#<<< PLACE YOUR CODE ABOVE THIS LINE.

@register                                    # generated
class Post(ho_baseclasses.BC_BlogPost):
    """
    FIELDS:
    - id:        (uuid) NOT NULL
    - title:     (text) NOT NULL
    - content:   (text)
    - published: (bool) NOT NULL
    - author_id: (uuid)

    PRIMARY KEY (id)
    FOREIGN KEYS:
    - _reverse_fkey_blog_blog_comment_post_id: ("id")
    - post_author_id_fkey: ("author_id")
    """
    #>>> PLACE YOUR CODE BELOW THIS LINE.    # developer zone (class level)
    Fkeys = {
        'rfk_comments': '_reverse_fkey_blog_blog_comment_post_id',
        'fk_author':    'post_author_id_fkey',
    }
    #<<< PLACE YOUR CODE ABOVE THIS LINE.

    def __init__(self, id=None, title=None, content=None,   # generated
                 published=None, author_id=None, **kwargs):
        super().__init__(id=id, title=title, content=content,
                         published=published, author_id=author_id, **kwargs)
        #>>> PLACE YOUR CODE BELOW THIS LINE.
        # developer zone (__init__ + business code)
```

Drift becomes structurally impossible inside this workflow, because there is no
state in which the generated zone is stale: it's rewritten on every patch, and
rewriting it can't cost you anything, because your code isn't in it.

Note where the developer zone sits, by the way. It's where the business methods
from [part 4](predicate-locality.md) go: the predicate-locality
pattern isn't a convention you have to remember, it's where the tooling puts the
cursor.

## What a change actually looks like

Add a `NOT NULL` constraint to `blog.post.author_id`:

```console
$ half_orm dev patch create 7-post-author-id-should-be-not-null
$ cat > Patches/7-post-author-id-should-be-not-null/00_author_id_not_null.sql
alter table blog.post alter column author_id set not null;
$ half_orm dev patch apply
$ git diff
--- a/blog/blog/post.py
+++ b/blog/blog/post.py
@@ -36,7 +36,7 @@
     - title:     (text) NOT NULL
     - content:   (text)
     - published: (bool) NOT NULL
-    - author_id: (uuid)
+    - author_id: (uuid) NOT NULL

     PRIMARY KEY (id)
```

One line changed, in the generated zone. The `Fkeys` block two screens down is
untouched. Then you write the business code and tests that use the new
constraint, and commit. That single commit contains the SQL patch, the
regenerated generated zones, and the new application code.

Schema version and code version cannot drift, because they are the same commit.
That's the atomicity problem, gone, without a deployment checklist.

## Git as the authority, not a migrations table

Every half-orm-dev project is already a git repository. Python source, generated
classes, business methods, and schema patches are all tracked together. So:

- `git diff v1.3.4..v1.4.0` shows the schema delta and the code delta in one
  reviewable diff.
- `git blame` tells you when a column was introduced and by whom.
- `git bisect` can find the patch that broke a schema-sensitive test.

None of that needs tooling beyond git.

The branch model:

```
ho-prod ─────●──────────────────────────────────●──────────►  (tags: v1.4.0)
              \                                /
   ho-release/1.4.0 ●──────────●──────────────●
                     \        /
        ho-patch/7-... ●────●
                             └─ merge moves Patches/7-.../ into Patches/staged/
                                and renames the branch to ho-staged/7-...
```

`half_orm dev release create minor` forks `ho-release/X.Y.Z` from `ho-prod`.
`half_orm dev patch create N-name` forks a patch branch from the release.
`half_orm dev patch merge` restores the production state, applies the
accumulated patches, runs the full test suite (a failure aborts the merge), and
on success merges into the release, renames the branch to `ho-staged/N-name`,
and moves the patch directory from `Patches/N-name/` to
`Patches/staged/N-name/`. Repeat for as many patches as the release needs.
`half_orm dev release promote prod` merges into `ho-prod`, tags `vX.Y.Z`, and
deletes the staged and release branches.

That relocation is worth a word, because the reason is ergonomic rather than
technical. A patch directory sits under `Patches/` while it is a candidate,
under `Patches/staged/` once merged into a release, and under
`Patches/orphaned/` if it is detached from one. Without the move, `Patches/` and
the `ho-patch/` namespace accumulate every patch the project has ever produced,
and what a developer needs to see (what is still in flight) ends up buried in
what is already settled. Status becomes readable from the layout instead: what
sits directly under `Patches/` is what remains to be merged.

The branch rename has a different motive. `ho-staged/N-name` holds nothing the
release branch does not already have, and it is kept anyway: a merge that failed
or completed only in part can still be examined afterwards, and a patch can
still be backed out while its release is open. Once the release is promoted,
nothing in it can move, and the staged branches go with it.

The tag *is* the schema version. The sequence of patch directories between two
tags *is* the migration path.

This is where the difference from Flyway and Liquibase is sharpest. In those
tools the migrations table in the database is the authoritative record of what
has been applied; lose it and the tool can't compute what remains to run. In
half-orm-dev that authority is git's. `half_orm_meta.hop_release` is a version
stamp written *after* a successful upgrade, a derived record, not an input to
the next computation.

Deploying a *new* instance is `half_orm dev clone`, which the next section
covers. Upgrading an *existing* one is three steps with nothing to synchronise between
them: pull, `half_orm dev upgrade`, restart. `half_orm dev upgrade` reads the current
version from the metadata table and applies every patch between it and the
target tag. It performs no regeneration at all: the Python model comes from the
tag checkout, so schema version and code version are consistent by construction
rather than by procedure.

Rollback is a branch switch, covered below with the branches it switches
between.

## A checkout is a working instance

Everything so far says git holds the *record*. What makes that more than a
filing claim is that the record is complete enough to instantiate.

Promoting a release to production writes a snapshot of the database into
`.hop/model/`, committed and tagged with everything else:

```
.hop/model/
├── schema.sql          # relative symlink to the current version
├── schema-1.3.4.sql    # structure, from pg_dump --schema-only
├── data-1.3.4.sql      # the reference data the release's patches inserted
├── schema-1.4.0.sql
└── data-1.4.0.sql
```

Restore those two files into an empty database and you have that release,
running. No patch replay, no migration order to respect, nothing to seed. A
repository checkout is not a recipe for the database; it *is* the database,
alongside the schema patches that produced it, the generated model, the
business code and the tests.

That single artefact serves two audiences who are normally served separately,
and it serves them with the same command. Production deploys a new instance
with `half_orm dev clone --production`, which restores the snapshot and then
runs the `bootstrap/` scripts for what is specific to that instance. A developer
joining the project runs the same command without the flag, gets the same
structure and the same reference data locally, and every `patch apply` rebuilds
from that snapshot before replaying the release's staged patches. The
environment a developer tests against and the one operations deploys are
produced from the same committed bytes, one flag apart.

It also explains the rule from earlier about where reference data belongs. A
patch that inserts a system role as idempotent DML is captured in the next
snapshot automatically, because the dump takes data as well as structure. It
therefore reaches every future instance without anyone running anything, which
is precisely what `bootstrap/` scripts, running once per instance and never
captured, cannot do.

Only production versions are snapshotted. Release candidates and staged states
are not, hotfixes overwrite the version they fix, and git keeps the earlier
snapshots for as long as the history does.

## What production checks out

The branch diagram above is the development side. A production server sees a
different shape:

```console
$ git branch
  ho-prod
  ho-prod-1.3.3
  ho-prod-1.3.4
* ho-prod-1.4.0
```

Promoting a release creates `ho-prod-X.Y.Z` from the tag and pushes it. The
branch is immutable: nothing is ever committed to it afterwards. A server checks
one out and runs it, which is why deployment needs no git write access anywhere
on the machine, and why the starred branch is a sufficient statement of what
that server is running.

Because each of those branches carries its own `.hop/model/` snapshot,
`ho-prod-1.3.4` is not merely a label for a past release: check it out and the
schema, the reference data, the generated model and the code of 1.3.4 are all
there together. That is what makes rollback a branch switch. `half_orm dev
rollback` restores the snapshot taken before the last upgrade and checks out the
branch it belongs to, with `--to-version` to go further back. Nothing is
rewritten and no inverse migration is computed: you return to a state that was
released rather than to one reconstructed from deltas.

Three versions are kept. Promotion prunes the older ones from the remote, so the
listing above is not an accumulation but the retention window itself.

This is also what a migrations table cannot give you. Reconstructing an old
state there means replaying the project's deltas from its first commit onward
and hoping each one still runs. Here it means checking out a tag.

## Tests run against a real schema, always

The workflow has a side effect. After `half_orm dev patch apply`, your local
database *is* the patched schema, so tests written at that point exercise the
new constraints against real PostgreSQL behaviour. At merge time the suite runs
against the schema production actually runs.

Because halfORM never interposes a mock between Python and PostgreSQL, any test
that calls a terminal method exercises the live database including its integrity
constraints. Which means missing or mis-scoped constraints are *testable*: a
`NOT NULL` that should exist and doesn't, a `UNIQUE` index that's too broad or
too narrow, an absent foreign key. You attempt the operation and assert that
psycopg3 raises `IntegrityError`. Schema correctness becomes something your test
suite covers, with no infrastructure beyond pytest.

Meanwhile the predicate-structure tests from [part 4](predicate-locality.md)
need only a schema-consistent database, not populated data. `half_orm dev patch
apply` also generates a read-only base test per relation that checks it's
instantiable, that it subclasses `Relation`, and that every declared `Fkeys`
alias points at a real PostgreSQL constraint and returns a `Relation`. Break an
alias with a patch and the suite tells you at merge time.

## What this costs

**Workflow compliance is required.** This is the one genuinely soft guarantee in
the whole design. The runtime dissolutions from earlier posts are model-level:
you can't write an N+1 because the mechanism doesn't exist. This one is
procedural: it holds as long as every schema change goes through a patch. A DBA
who runs `ALTER TABLE` directly against production breaks the version invariant,
and the divergence has to be reconciled before the next patch applies. If your
organisation can't commit to that, you get much less out of this than the design
promises.

**History is strictly linear.** Long-lived feature branches that evolve the schema
differently from `ho-prod` are not supported. That's the price of the co-deployment
guarantee: a linear, fully audited schema history is what makes "pull, upgrade,
restart" safe.

**No automatic down-migrations.** Rollback returns you to a release that
shipped, not through an inverse of the change you are undoing. For a lot of
schema changes that's
the honest answer anyway (an automatically generated down-migration for a
destructive DDL statement is frequently a comforting fiction), but if your
process depends on reversible migrations, this is a real difference.

## The through-line

Six essays, one idea: give the schema exclusive authority, and the problems that
come from splitting authority stop existing.

At runtime, that means no identity map, no session, no lazy loading, no N+1, no
proprietary query language: not because those were solved, but because the
concepts they need have no counterpart in a schema-first relational model. Over
time, it means schema and code in one commit, patches in plain SQL, git as the
authoritative history, and a checkout that carries the database rather than
instructions for rebuilding it.

Ted Neward's essay ended by observing that the traditional answers to the
impedance mismatch amount to "effectively 'solving' the problem by ignoring one
half of it." He meant that as a criticism.

halfORM covers exactly half of SQL: the data-manipulation half. It has nothing
to say about `CREATE TABLE`, and that's the point: DDL belongs to the database
and the people who administer it. I'd argue that's the right half to cover, and
that covering it well is enough.

---

*half-orm-dev lives in its own repository: [half-orm/half-orm-dev](https://github.com/half-orm/half-orm-dev).*
