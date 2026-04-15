# 1.0.0rc1 (2026-04-15)

## Breaking changes

- **`ho_get()`** returns a `dict` directly and raises `NotFoundError` (0 rows)
  or `MultipleRowsError` (> 1 row). The old behaviour (private method returning
  a relation) is removed.
- **Deprecated query builders removed** — `ho_limit`, `ho_offset`, `ho_order_by`,
  `ho_distinct` no longer exist as property setters. Use keyword arguments to
  `ho_select()` instead.
- **`FKEYS_PROPERTIES` / `FKEYS`** class attributes removed. Use `Fkeys` only.
- **`ho_cast()`** raises `CastError` if the target is not in the PostgreSQL
  inheritance hierarchy.

## Changes

* docs(fkey): document explicit Fkeys dict format for views (3c86ed7)
* feat(relation): add explicit Fkeys dict support for views (views-fkeys) (52977b2)
* feat(relation): implement inheritance check in ho_cast + add CastError (6851336)
* refactor(relation)!: remove FKEYS_PROPERTIES/FKEYS compatibility check (415831e)
* refactor(relation)!: remove deprecated API and dead code for 1.0.0 (4944f83)
* feat(relation)!: refactor ho_get to LIMIT 2 + add ho_aget (87ef8cb)
* feat(relation)!: ho_get() returns dict and raises NotFoundError/MultipleRowsError (027870d)
* refactor(sql_ast): complete AST integration for compound SELECT statements (9eb605f)

# 0.18.13 (2026-04-14)

* fix(relation): use UNION/EXCEPT SQL for | and - when FK joins are present (1e28437)

# 0.18.12 (2026-04-12)

* feat(field): add Expr class and column-to-column comparisons (7286e79)
* feat(relation): add ho_copy/ho_acopy bulk load methods (700e0eb)
* ci(block-merge): set explicit empty permissions on GITHUB_TOKEN (645dd18)
* docs(api): document async raw SQL methods in model.md (0168695)
* feat(model): add aexecute_function and acall_procedure async methods (f570995)

# 0.18.11 (2026-04-04)

* fix(relation): prevent silent mass-delete/update when using FK navigation (8973324)
* docs(relation): document FK navigation in ho_assert_is_singleton (a00d366)
* ci: add title input to workflow_dispatch and fix broken doc links (aaeff38)
* build: push git tag to remote on publish (52414fb)

# 0.18.10 (2026-04-03)

* feat(relation): ho_assert_is_singleton() recognises FK-constrained identifiers (fecc614)
* docs: document python -m half_orm CLI in the half-an-hour guide (b1c9724)
* fix(relation): ho_is_set() propagates through FK joins (2fb91ec)
* fix(relation): ho_is_set() propagates correctly through set operators (04a8c02)
* docs: fix async→sync counterpart anchor links in relation.md (f0e3766)

# 0.18.9 (2026-03-31)

* feat(fkey): set(Relation|fields) — no import required for related class (d2b9afb)

# 0.18.8 (2026-03-31)

* feat(fkey): set() without argument joins against all rows of related table (cf0c139)
* feat(json_agg): support chained FK (A ← B → C) in ho_select (json_agg) (d5e4692)
* ci: auto-cleanup stale doc versions on tag push (a776c84)
* feat(doc): add breaking change for json_agg return value with singleton and direct fkeys. (a29fb39)

# 0.18.7 (2026-03-30)

* feat(fkey)!: direct and singleton reverse FK in json_agg now return dict, not list (4bfbaf8)
* docs: enrich async executors section and fix get_relation_class example indent (doc) (b27aecd)
* feat(docs): Add ref to transaction.md in relation.md (016fbe5)
* fix(docs): syntax highlighting of examples (b08eaf7)
* ci: deploy dev docs on push to doc branch (aa3fc4c)
* fix(docs): remove unnecessary '::' (6190ed6)
* fix(relation): ho_is_set() returns True when any FK is joined; warn in docs (0bac479)
* docs: remove Quick Start, Fundamentals and Tutorial from nav (9de4dec)
* docs: fix connection config section in half-an-hour (e3a90eb)
* docs: use U+2223 (∣) instead of | in quick reference table cell (0b44bb6)
* docs: add ^ to intro; fix | rendering in quick reference table (472cf07)
* docs: add XOR operator, API Reference nav, and rewrite transaction.md (c1cbadb)

# 0.18.6 (2026-03-27)

* docs: replace .. versionadded/versionchanged with *New/Changed in version X.* (6f2034c)
* docs: enable griffe-sphinx for .. versionadded/versionchanged rendering (0a16cd7)
* docs: fix quick reference table in half-an-hour (addf464)
* docs: rewrite fkey.md and fkey.py docstrings (dffd9d7)
* docs: add .. versionadded/versionchanged annotations to docstrings (efb9603)
* fix(docs): fix algebra example and desc docstring formatting (0efefd1)
* docs: rewrite model.md and model.py docstrings; add register_class docstring (9bfaf51)
* docs: mark SQL-executing methods with *Executes SQL.*; move ho_assert_is_singleton to Introspection (243b111)
* docs(api/relation): fix TOC hierarchy and ho_insert example format (acf2774)
* docs: rewrite api/relation.md; sync DC_Relation stubs; improve module docstring (b762fe2)
* docs: improve docstrings for guide methods; add API links in half-an-hour (cb082c3)
* docs(mkdocs): add half-an-hour guide to navigation (25638bc)
* docs: rewrite README and index; document @register in half-an-hour guide (afbfce4)
* feat(docs): add Learn half-orm in half an hour (3f2a671)
* fix(relation): _ho_pkey falls back to first UNIQUE NOT NULL when no PRIMARY KEY (88b74be)
* feat(relation): add ho_select(json_agg=...) for LEFT JOIN aggregation (e30ded3)
* feat(relation): remove unnecessary conversion to dict (a1d6997)
* feat(github): prevent merge of maintenance branches on main (9d28018)
* feat(fkey): detect fkey cycles (d791fd6)
* fix(doc): fetch gh-pages from origin (doc) (dd8df29)
* fix(make): add --tags to git describe (tag: v0.18.5) (1caa456)

# 0.18.5 (2026-03-25)

* feat(makefile): add tests before build and publish. Allow publish only on releases. (8383972)
* fix(relation): remove false fkey from repr (join) + tests. (a8dd99e)
* feat(relation): repr now includes fkeys attributes names in Fkeys (80e41b2)
* refactor(relation): remove ho_limit internal calls from count methods (docs-workflow) (ec4ef46)
* fix(ci/docs): add alias input to workflow_dispatch for setting latest (5838613)
* fix(ci/docs): replace multiline python with one-liner in cleanup step (ebd5622)
* Revert "fix(ci/docs): parse mike list --json to extract version identifiers" (1a6e79b)
* fix(ci/docs): parse mike list --json to extract version identifiers (7078a78)
* ci(docs): add workflow_dispatch trigger with version rebuild and cleanup (416fc7b)
* docs: fix version reference and consolidate mike versions by minor (4134bc8)
* docs(readme): mention 0.17.x branch maintained for psycopg2 users (6188085)

# 0.18.4 (2026-03-20)

* feat: per-thread psycopg connections via threading.local() (be44f70)
* feat: raise ReadOnlyRelationError on DML operations against views (c185a57)

# 0.18.3 (2026-03-19)

* fix: unwrap Field objects inside lists and force TEXT format in FieldDumper (81dc8cc)

# 0.18.2 (2026-03-19)

* fix(null): update FieldDumper for psycopg 3.2+ API compatibility (7480557)

# 0.18.1 (2026-03-19)

* fix: handle nested Field objects as query parameters (a2d48f5)
* feat(CI): replace psycopg2 by psycopg[binary] (da24543)
* Add breaking changes to README + CHANGELOG (7c012df)
* feat(tests): add async tests (9be689f)

# 0.18.0 (2026-03-19)

## ⚠️ BREAKING CHANGE — psycopg2 → psycopg 3

halfORM 0.18 **drops psycopg2** and requires **psycopg 3** (`psycopg[binary]`).

### Migration guide

```bash
pip uninstall psycopg2-binary
pip install "psycopg[binary]"
```

If you register custom psycopg2 adapters in your own code (e.g.
`psycopg2.extensions.register_adapter`), you must rewrite them using the
psycopg 3 `Dumper` / `Loader` API. See the
[psycopg 3 adaptation docs](https://www.psycopg.org/psycopg3/docs/basic/adapt.html).

Notable psycopg 3 differences that may affect your code:

| psycopg2 | psycopg 3 |
|---|---|
| `psycopg2.connect(…, cursor_factory=RealDictCursor)` | `psycopg.connect(…, row_factory=dict_row)` |
| `conn.get_dsn_parameters()['dbname']` | `conn.info.get_parameters()['dbname']` |
| `IN %s` with a tuple | `= ANY(%s)` with a list |
| `cursor.mogrify()` on any cursor | `ClientCursor(conn).mogrify()` |
| `psycopg2.extras.Json` for dicts | `conn.adapters.register_dumper(dict, JsonbDumper)` |

### New in 0.18 — async support

Six async executor methods are now available (`ho_ainsert`, `ho_aselect`,
`ho_aupdate`, `ho_adelete`, `ho_acount`, `ho_ais_empty`). They require an
explicit async connection:

```python
await model.aconnect()   # open async connection
# … await rel.ho_aselect() …
await model.adisconnect()
```

See the [Async Support section in the README](README.md#async-support) for a
full example.

---

* feat(doc): exemples for async usage (8822ecb)
* feat(async): add ho_a* async methods and factorize query preparation (fcaed69)
* refactor: migrate from psycopg2 to psycopg 3 (78da47e)
* test(algebra): insert isolated test persons with POOL letters and TEST_DATE for deterministic set algebra (main) (b3063bd)
* feat(relation): add ho_where_display method (ast) (048c210)
* feat(transaction): add savepoint support for nested transactions (6f450da)
* feat(relation): auto-expose foreign keys as fk_/rfk_ attributes (7c8e114)
* feat(relation): add unique not null constraint to check singleton. (2ee7850)
* refactor(sql): replace string concatenation with AST-based query construction (da21e7c)
* feat(relation): add ho_assert_is_singleton method. (e196765)
* feat(relation): remove 1=1 from generated SQL when there is no constraint on the Relation object (a3a18a5)
* feat(relation)!: rewrite @singleton to check PK intention without DB query (aafb891)
* feat(relation): auto-deduplicate ho_select results when JOINs produce duplicate PKs (71ad935)
* refactor(relation): deprecate mutating select methods in favor of ho_select parameters (4da51cc)
* feat(test): add docstring to algebra tests. (0133285)
* feat(relation): explicitly set Relation as an unhashable type. (8cea766)
* fix(relation): remove duplicate JOIN conditions in generated SQL. (35b530f)
* update(docs): remove the references to ho_get (6006b57)
* feat(utils): add replacement message to _ho_deprecated (885accc)

# 0.17.7 (2026-03-10)

## BREAKING CHANGE

Relation method ho_get is now private (_ho_get) and has been marked deprecated. It was
an anti-pattern. Use @singleton decorator instead.

* deprecate(relation): deprecate ho_get in favor of @singleton decorator (f6ecff4)
* feat(relation): redefine equality as (A - B) | (B - A) == ∅ (3307892)
* fix(ci): remove python3.7 from tests on gitlab + add python3.14 (bf42640)
* fix(ci): ignore coveralls errors. (0d03f19)

# 0.17.6 (2026-25-02)

* fix: improve error handling and connection error messages (631e0ad)
* fix: include config file info in database connection errors (8edf683)
* fix(cli): remove unused  import from importlib.metadata. (2e0b54d)
* build(deps-dev): bump cryptography from 44.0.1 to 46.0.5 (c18f01c)
* fix(readme): license is GPL-3.0 not LGPL-3.0. (bb72cc2)

# 0.17.5 (2026-30-01)

* fix: [half-orm-dev] check False string in connection file for production param. (e8a967f)

# 0.17.4 (2026-27-01)

* fix: [half-orm-dev] production mode is set with production key (not devel) (1a157ae)

# 0.17.3 (2026-27-01)

* rename.Model.__production_mode to Model._production_mode. (3f66994)
* rename Model.__dbinfo to Model._dbinfo. (3a92e4a)
* build(deps-dev): bump jaraco.context from 5.3.0 to 6.1.0 (203ca12)
* build(deps-dev): bump virtualenv from 20.26.6 to 20.36.1 (4095cb8)
* ci: add Python 3.14 (60b83f1)

# 0.17.2 (2026-08-01)

* feat: use functools.wraps in relation.transaction decorator. (3986912)
* build(deps-dev): bump urllib3 from 2.6.0 to 2.6.3 (a974ebf)

# 0.17.1 (2025-18-12)

* feat(cli): improve error messages for unknown commands (16d6575)
* build(deps-dev): bump filelock from 3.16.1 to 3.20.1 (ff5155a)
* build(deps-dev): bump urllib3 from 2.5.0 to 2.6.0 (3b40923)

# 0.17.0 (2025-17-11)

* docs: add model.sql_trace documentation. (5a483e8)
* feat(trace): add SQL trace mode with caller context (5499a57)

# 0.16.4 (2025-06-11)

* docs(relation): add type hints to DC_Relation protocol methods (17f8448)
* feat(cli): add error handling wrapper for extension commands (20737e0)
* fix: ho_limit(0) was returning all the lines in the relation. (b7f2a05)
* tests: add PostgreSQL 18. (93e44b8)

# 0.16.3 (2025-03-11)

* feat(cli): add debug mode for extension errors (16f668d)

# 0.16.2 (2025-09-10)

* feat: Add direct command support to CLI extension system (c9ee263)
* fix: inherit from registered classes in PostgreSQL table inheritance (1638f89)
* ci: gitlab fix missing dependency (59a3da8)
* ci: remove dummy_test for gitlab. (569f208)
* docs: collorg/halfORM -> half-orm/half-orm (eb2a764)

# 0.16.1 (2025-08-18)

* cli: use _ in package_name (0de9904)
* docs: fix lists and code inside code. (70bcf48)
* tests: fix test_discover_extensions_version_incompatible. (bf6bbf1)
* test: temporarily skip test_discover_extensions_version_incompatible (98c3518)
* build: add flake8 linting to test target (f039242)
* fix(flake8): Remove global _trust_extension from cli.warn_unofficial_extension (e0e99e1)

# 0.16.0 (2025-07-05)

## Added
- **CLI Extension System**: Complete extensible CLI framework for halfORM
  - Automatic discovery and loading of `half-orm-*` extension packages
  - Security system with official/trusted/unofficial extension categories  
  - Version compatibility checking and trust management
  - Unified `half_orm` command that aggregates all extensions
  - New `cli_utils` module for extension developers
  
  See documentation (wip) for extension development guide and usage details.

* refactor: remove unused extension registration functions (64a8ce2)
* docs(wip): refactor CLI and extension documentation (bd1c41d)
* feat(cli): improve extension discovery and metadata handling (3bd2106)
* feat: unified CLI with extension discovery, security, and version compatibility (bc457bd)
* docs: upgrade docs/index.md (e1213b9)
* Update issue templates (667338a)
* Revert "github: Issues and PR Templates." (688d513)
* docs: add halfORM Extensions description for 0.16.0 (6f8ffb3)
* github: Issues and PR Templates. (964e0a1)
* docs: update tutorial First Steps for 0.16.0 (2da2fb6)
* docs: update tutorial installation for 0.16.0 (df200bf)
* docs: upgrade quick-start to 0.16.0 (519503d)
* docs: update Quick Start Guide for halfORM 0.16 CLI (517afcc)
* ci: fix Bash Pattern Matching. (a15d23c)
* docs: remove duplicates in documentation-workflow (41ee7b7)
* fix: improve default version handling in documentation workflow (tag: v0.16.0-rc3, tag: latest) (4b68926)

# 0.16.0-rc (2025-07-05)

* docs: upgrade docs/index.md to 0.16 release. (0e6230d)
* fix: force dev as default version for mike deployment (tag: v0.16.0-rc1) (fb7b8a5)
* fix: utils.warning test. (4d3acfc)
* fix: correct mike deployment command for dev version (0bf32c9)
* feat: implement multi-version documentation system (f40d2b1)
* WIP: Add unified CLI system and ecosystem foundation (ee12fd3)
* docs: Add entry for Instant API. (cli) (9576d52)
* docs: Add Instant Rest API Example. (af3cbf9)
* docs: enhance GitLab example with loose foreign keys pattern analysis (59ac65e)
* examples: add gitlab examples. (6d6fa98)
* docs: add Method Categories: Builders vs Executors section. (bfd9ea2)
* docs: add Database Exploration with GitLab example. (5ffe712)
* tests: add tests for __main__.py (5c188ab)
* docs: remove between (not implemented) from the doc. (0b4c1a1)

# 0.15.1 (2025-07-01)

* Add CLI args for database/relation inspection in __main__.py (950aebf)
* Add documentation and project URLs to PyPI metadata (a99b2b5)
* docs: more about NULL. (a64585b)
* docs: note about count and very large tables + use of NULL value. (fdce8f2)
* docs: fix typos. (2660f18)
* feat: add relation _ho_ukeys attribute. (73d4921)
* docs: add Fundamentals section. (42294f7)
* Point diagnostic tool to specific database configuration help (16bd773)
* docs: improvements. (5d84642)
* docs: add Tutorial part Models and Relations. (ec07054)
* docs: add Tutorial First Steps (fa44017)
* feat: enhance database exploration with relation comments (09244aa)
* feat: add diagnostic command python -m half_orm (0dcdc6b)
* docs: add tutorial index (fc6fd01)
* docs: fix PostGIS example and improve querying example (65b22e9)
* docs: use standard emojis. (7c0edc3)
* docs: add version indicator and enhance homepage with 0.15.0 details (db0d3ed)
* docs: add homepage and update documentation links (3189e83)
* ci/cd: fix missing permissions for the GITHUB_TOKEN. (b18acca)
* ci/cd: deploy doc on collorg.github.io/halfORM (2ade9c8)
* ci: fix permissions security alert (7ab4a47)
* Bump urllib3 from 2.4.0 to 2.5.0 (a795cf3)

# 0.15.0 (2025-06-27)

## BREAKING CHANGE

**HOP Packager Moved**: The `hop` command and packaging functionality has been moved to a separate package `halfORM_dev`. 

If you were using the `hop` command, please clone https://github.com/collorg/halfORM_dev.

* chore: remove unused dependencies click and GitPython (6ea30e1)
* feat: add @register decorator for custom relation classes (61d8fb8)
* docs: Add quick start. (a24f8c7)
* docs: half_orm only deals with PosgreSQL databases. (194ce7f)
* docs: modernize README and add complete documentation skeleton (232e8e2)
* refactor: remove HOP packager - moved to halfORM_dev (b16ab60)
* [hop] Fix sync-package (c999449)
* Bump requests from 2.32.0 to 2.32.4 (4ce1d6d)
* [CI] Fix workflows permissions. (ee12aa4)

# 0.14.0 -- hop 0.1.0 alpha 23 (2025-05-20)

* [hop] Remove call to db_conn.set_params if there is no config file. (cc825a1)
* [model][hop] Try to use trust authentication if there is no config file. (ca69599)
* [CI/gitlab] Use bookworm image. (a0569f9)
* [CI/github] Use ubuntu 24.04 image. (ac9a1d6)

# 0.13.10 -- hop 0.1.0 alpha 22 (2025-03-24)

* Check if a value is in an array type column. (1a6dd01)

# 0.13.9 -- hop 0.1.0 alpha 22 (2025-02-12)

* Bump cryptography from 43.0.1 to 44.0.1 (b53d88d)
* Pass a list as Field value to select the entries in the list. (916c334)

# 0.13.8 -- hop 0.1.0 alpha 22 (2025-01-15)

* Update licence date.
* [hop] Fix: add missing kwargs in arguments transmitted to the parent table. (ddbe18f)
* Bump virtualenv from 20.25.1 to 20.26.6 (e09fc9e)
* [github/CI] Use ubuntu-22 (Python 3.7 not present on ubuntu-24). (38212e8)

# 0.13.7 -- hop 0.1.0 alpha 21 (2024-11-29)

* [hop] Fix bug with pg enum types. (3e3e0fe)

# 0.13.6 -- hop 0.1.0 alpha 20 (2024-11-26)

* [model] Reload now clears cached classes. (2f94c6e)
* [relation] Fix warning messages for invalid field names. (be1874c)
* [hop] Add missing line. (e536451)
* [relation] Replace the error message with a warning for fields with invalid identifiers. (b7afb93)
* [model] Added fields_aliases argument to get_relation_class to handle column names that are Python keywords or invalid variable names. (994e3a0)
* [hop] Add sql_adapter module if missing. (e643ba8)
* [field] Use cast in where representation to handle user-defined domains. (188e06b)

# 0.13.5 -- hop 0.1.0 alpha 19 (2024-11-21)

* [hop] Add '**kwargs' to deal with inheritance. (1ab8952)
* [hop] Fix ho_dataclasses pb with columns named 'field' (ce626c1)
* [test] Fix deprecation warning re.sub Python3.13. (9ee907a)

# 0.13.4 (2024-11-18)

* Add python3.13 to setup.py (47e9371)
* [readme] Add licence badge. (fc050ed)
* [test] test utils._ho_deprecated decorator. (af8cde9)
* [fkeys] Fkey.set method now returns self. Fix bug with cast and reverse keys. (20978d2)
* [sql_adapter] a little more genericity for postgresql lists -> python transtyping (4882a03)
* Move sql_adapter. (7534efb)
* [requirements] Update. (ce8737f)

# 0.13.3 -- hop 0.1.0 alpha 18 (2024-11-11)

* [relation] New relation.transaction decorator (replaces Relation.ho_transaction). (07f3a07)
* [relation] Replace attribute _model by _ho_model. (8d55b6a)
* [test] ho_distinct argument values. (d45242c)
* [test][relation] test dict behavior (keys, items and __getitem__). (076139f)
* [test] utils. Fix CI (9e5223f)
* [test] utils. (8f0352d)
* [test] ho_count with fkeys. (8928400)
* [hop] Pylint score improvement (8d218c9)
* [hop] Add repo base dir to PYTHONPATH. (064576f)
* [field] Add missing import. (63c24dd)
* [test][relation] ho_freeze and ho_unfreeze (4bcb2f5)
* [relation] Reintroduction of deprecated methods to be remove with release 1.0.0 (680cd5f)
* [relation] refactor ho_count. (89d2f5d)
* [sonarcloud] More fixes. (a99e57d)
* [refactor] Fix some issues pointed out by Sonarcloud. (b106f74)
* [relation] Use context manager for cursors. (2260f32)
* [hop] Replace kwargs with the explicit list of fields. (b947737)
* [field] Adds the Field.py_type property returning the Python type corresponding to the SQL type. (ee0202e)

# 0.13.2 -- hop 0.1.0 alpha 17 (2024-10-31)

## BREAKING CHANGE

Relation methods select, insert, upgrade, delete deprecated in 0.8.0 have now been removed. Use ho_select, ho_insert, ho_upgrade and ho_delete instead.

* [hop] sort imports in ho_dataclasses.py (801385b)
* [hop] Add Fkeys to dataclasses. (10ba318)
* [hop][relation] Refactor. Add DC_Relation to improve developper experience. (a9e2dda)
* [CI] Keep psycopg2 2.9.9 to preserve Python 3.7 compatibility. (f9c0380)
* [CI] Bump to psycopg 2.9.10 for Python 3.13 compatibility. (e092e3b)
* [CI/Github] Fails with Python 3.13. (2a2d897)
* [CI/Github] Add PostgreSQL 17 (1699e1a)
* [CI] Add Python 3.13 (7687c5e)
* [BREAKING CHANGE] Python 3.6 is no longer supported (89f49c1)
* [hop] Use of dataclasses to improve developer experience. (a61beb0)
* [test] coverage utils. (66b64bb)

# 0.13.1 -- hop 0.1.0 alpha 16 (2024-09-11)

* [test] Test utils.check_attribute_name. (521c922)
* [hop] Fix: empty keys in Fkeys were taken into account when generating relation class attributes. (dba5b22)

# 0.13.0 (2024-09-10)

## BREAKING CHANGE

As of version 0.13, the `Relation.ho_transaction` decorator is deprecated and replaced by
the `Transaction(<model>)` context manager (see the [readme](https://github.com/collorg/halfORM?tab=readme-ov-file#dml-the-ho_insert-ho_select-ho_update-ho_delete-methods)).

* [readme] remove deprecated ho_transaction example. (ac423af)
* [field] Marks the deprecated _unset method as not to be tested. (1f5a278)
* [transaction][BREAKING CHANGE] Transactions are now managed by a context manager. (628ceb2)
* [relation] The Relation._model object must be the one used to generate the relation class. (2bdcdb7)
* [test] Add -s option to pytest. (a7c3be0)
* [field] Do not use deprecated _unset method to clear field. (6cc2dce)

# 0.12.1 -- hop 0.1.0 alpha 15 (2024-09-06)

* [field][BREAKING CHANGE] list and set values are cast to tuples. (e215d1a)
* [relation] Remove __cursor attribute. (1d205bb)
* Bump cryptography from 42.0.5 to 43.0.1 (fee3fb6)
* [hop][relation] Emmit a warning if a column is a Python keyword or not a valid attribute name. (cfff9ef)
* [relation] __len__ will be removed in the release 0.13. Warning message with location issued when used. (00e093c)

# 0.12.0 (2024-08-28)

## BREAKING CHANGE

 From version 0.12 onward, the *`Relation.__len__`* method has been deprecated.
 It is replaced by the `Relation.ho_count` method.

*The code `len(Person())` must be replaced by `Person().ho_count()`*.

> The problem was that the Python builtin function `list` triggers the `__len__` method if it exists. So the
> code `list(Person())` was triggering two requests on the database : frist a SQL `select count`
> and then the SQL `select`.


* [hop] Remove git diff from dummy_test.sh (c8e3bd8)
* Add requirements-dev.txt (1047292)
* Code cleanup. (89fc6da)
* [relation_factory] deprecated decorator has been moved to utils module. (37f25ef)
* [relation][BREAKING CHANGE] ho_count replaces __len__. (a7742af)
* [test] Remove duplicate test. (9440c19)
* Code clean-up (13f4be6)
* Remove examples directory. (a4bf44b)
* [relation] Fix wrong order of foreign key fields in relation representation. (c8abf92)
* [test] Coverage. (7b055b2)
* [fkeys] Detect loops in foreign key settings. (50068fa)

# 0.11.1 -- hop 0.1.0 alpha 14 (2024-08-23)

* [hop] Add field and foreign key declarations to allow autocompletion in IDEs. (cb5738c)
* Bump zipp from 3.18.1 to 3.19.1 (012d4ce)
* Bump certifi from 2024.2.2 to 2024.7.4 (5222b58)
* [readme] Add sql injection warning for the Model.execute_query method. (d729ead)

# 0.11.0 (2024-05-26)

## BREAKING CHANGE

The `ho_join` methode has been removed. Use foreign keys instead. The old code (see README):

```#python
lagaffe = Person(last_name='Lagaffe')
res = lagaffe.ho_join(
    (Comment(), 'comments', ['id', 'post_id']),
    (Post(), 'posts', 'id')
)
```

becomes:

```#python
res = []
lagaffe = Person(last_name='Lagaffe')
for idx, pers in enumerate(lagaffe):
    res.append(pers)
    res[idx] = {}
    posts = Person(**pers).post_rfk()
    res[idx]['posts'] = list(posts.ho_select('id'))
    res[idx]['comments'] = list(posts.comment_rfk().ho_select('id', 'post_id'))
```


* [README] Use of pepy.tech for download badge. (2764dc2)
* [README] ... (6188323)
* [README] Update links on badges. (e7a0ba2)
* --- updated-dependencies: - dependency-name: requests   dependency-type: indirect ... (ef93b05)
* Update README.md (219f194)
* Python 3.6 is not supported by github actions/setup-python@v5. Stop testing on github. Python 3.6 is tested on Gitlab. (3552ec3)
* [info] Python 3.6 is supported. (53a3d79)
* Update license. (c2b28e6)
* [doc] Why half_orm. (d4fb6b2)
* [relation][BREAKING CHANGE] Remove ho_join. See README.md. (76d44b1)

# 0.10.5 -- hop 0.1.0a13 (2024-05-07)

* [hop]  now generates the ho_dataclasses module containing a dataclass for each relation/view in the model. (57b0e84)

# 0.10.4 -- hop 0.1.0a12 (2024-04-30)

* [relation] Check that the value is valid for ho_limit an ho_offset methods. (cdc6e9b)

# 0.10.3 -- hop 0.1.0a12 (2024-04-30)

* [hop] Remove last reference to half-orm-packager in Pipfile template. (11b79a0)

# 0.10.2 -- hop 0.1.0a11 (2024-04-30)

* [hop] Remove references to obsolete half_orm_packager. (5b2a234)

# 0.10.1 -- hop 0.1.0a10 (2024-04-26)

* [hop] Fix. hop new was broken with devel option on an existing database. (02466c8)

# 0.10.0 -- hop 0.1.0a10 (2024-04-13)

* Remove dependency to pydash. (69e7fa2)
* [test] Adjust to one liners comments. (7f096fe)
* Cleanup. (a9365ac)
* Cleanup. (5922928)
* [relation][BREAKING CHANGE] Remove methods ho_group_by and ho_json. (a346236)
* Cleanup. (e8645e6)
* [test] Add test for relation defined by fkey. (997bca3)
* Cleanup. (044f640)
* [test] Remove duplicates in algebra test. (98c99e5)
* Cleanup. (41ea4e9)
* [hop] Do not check rebase twice. (56dfd11)
* Fix broken hop_test. (31df016)
* [WIP][model] Cleanup. (6ed901b)
* [WIP] Cleanup. (dc16ba1)
* Revert "[cleanup][hotest] Readability."" (848e7bd)
* Revert "[field] Clean-up." (60b2394)
* [cleanup][hotest] Readability." (a92bbda)
* [field] Clean-up. (7d141e2)
* [field] Mark _set method as deprecated. (ebaea77)
* [field][cleanup] Merge if statements. (a966ff9)
* [field][BREAKING CHANGE] Use of the set method is now mandatory to set the value of a field. (47c6c17)
* [Cleanup] Remove commented out code. (temp) (3f965d8)
* Bump idna from 3.6 to 3.7 (8a0f2b2)

## BREAKING CHANGES

Relation.ho_group_by and Relation.ho_json have been removed.

With version 0.10, it's no longer possible to set a field value directly.
You must use the `set` method to do so. Stay with version 0.9 until you have adapted your code.

### Before:

```py
Relation.field = value
```

### After

```py
Relation.field.set(value)
```

# 0.9.12 -- hop 0.1.0a10 (2024-03-29)

* [hop] Apply post patches after the modules generation. (41134a7)
* [fkeys] Add properties name and remote. (24ded98)

# 0.9.11 -- hop 0.1.0a9 (2024-03-11)

* [hop] Check that all hop_X.Y.Z in development can be rebased onto hop_main. (a8a2ea8)
* [hop][test] Move hop_test config directory. (1aaf9d9)
* [hop][prepare] Only restore database if database release is not the last release (AKA release in prod). (4561b5b)

# 0.9.10 -- hop 0.1.0a8 (2024-03-06)

* [pipenv] Bump cryptography to 42.0.5 (586ce19)
* [hop] prepare command (devel mode) now fails if the git repo is not clean. (39ebbaf)
* [github][CI] Remove misplaced matrix.postgresql-version (415b62e)
* [github][CI] Update actions to use Node.js 20 (github) (a4525c4)

# 0.9.9 -- hop 0.1.0a7 (2024-02-22)

* Bump cryptography from 42.0.2 to 42.0.4 (c02152e)

# 0.9.8 -- hop 0.1.0a7 (2024-02-06)

* [hop] Remove subprocess.run(['git', 'init' ... (870d5ae)

# 0.9.7 -- hop 0.1.0a6 (2024-01-10)

* Bump gitpython from 3.1.40 to 3.1.41 (746196d)
* [test] Remove unnecessary postgresql restart. (a99f336)
* [pipenv] Bump to Python 3.10. (bb31fb9)
* [make] Set LC_MESSAGES to C. (35931d4)
* [git] Ignore venv directories and files. (87b046d)
* [pipenv] Add pylance in dev mode. (4bce8e3)
* [test] Relation ho_description and ho_mogrify. Remove duplicate tests. (fd76802)
* Bump cryptography from 41.0.5 to 41.0.6 (a9fa76d)

# 0.9.6 -- hop 0.1.0a6 (2023-11-27)

* [error] Check error message on UnknownAttributeError. (43cc05a)
* [deps] Bump pydash to 7. (156d843)
* [relation] Check that args match column names before generating any sql. (b5e4028)

# 0.9.5 -- hop 0.1.0a6 (2023-11-21)

* [relation] @singleton decorator sets the attributes __is_signleton and __orig_args on the decorated function. (ff80877)
* [make] split tests. (23401ea)
* [CI][github] Add Python 3.12 and PostgreSQL 16. (fe4d43b)
* [CI][gitlab] Add Python 3.12. (9c8b863)

# 0.9.4 -- hop 0.1.0a6 (2023-11-14)

* [hop] Remove path from __init__.py. (bbdeed9)
* Bump gitpython from 3.1.34 to 3.1.37 (9c46991)
* Bump urllib3 from 2.0.5 to 2.0.6 (6f7c903)
* [make] Add target build. (0178a3c)
* Bump cryptography from 41.0.3 to 41.0.4 (d9e8d84)
* Update REAMDE (78ac59b)

# 0.9.3 -- hop 0.1.0a5 (2023-09-07)

* Bump gitpython from 3.1.32 to 3.1.34 (9735d3f)
* [hop] Remove gen-api command. (4fd4061)
* Bump gitpython from 3.1.31 to 3.1.32 (1289178)
* Bump cryptography from 41.0.2 to 41.0.3 (262d560)
* Bump certifi from 2023.5.7 to 2023.7.22 (ea2eceb)
* Bump cryptography from 41.0.0 to 41.0.2 (af58b62)
* [hop] Add base_dir to PYTHONPATH. (4a49763)
* [hop] Use subprocess.run to run the tests with pytest. Module doesn't behave as command. (cf910ad)

# 0.9.2 -- hop 0.1.0a4 (2023-06-09)

* [hop] Fix: wrong order in CHANGELOG. (c763300)
* Change the representation of a Relation object. (c2a18cb)
* [hop][WIP] Add gen-api command. (d2b180e)
* Add Makefile for test and build. (04ba7c2)
* [test] pipenv install pytest-cov. (5f3647e)
* Move utils.py to half_orm directory. (0b63fbd)
* Update README. (ec7c62c)
* [hop] The __init__ module of the package exports only the MODEL of the database. (69b4d74)
* [hop] Remove db_connector.py (5a00896)
* [model] Add the method classes. (badda81)
* [pipenv] Add twine. (782f0b1)

# 0.9.1 -- hop 0.1.0a3 (2023-05-22)

* [release] 0.9.1 (hop 0.1.0a3) (tag: 0.9.1) (a87bb21)
* [test] Upgrade halftest schemas half_orm_meta and half_orm_meta.view. (ed1769a)
* [hop] Refactor view "half_orm_meta.view".hop_penultimate_release. (ba401a3)
* [hop] Fix. Restore the correct DB release in case of error. (9b9acde)
* [hop] Print error message and exit if the database is missing. (72ac017)
* [hop] Add half-orm version to hop state. (2a1b504)
* [ci][github] Tests with postgresql 9.6 to 15 (Python 3.11). (44c180f)

# 0.9.0 (2023-05-12)

* [breaking][relation] Prefix methods with 'ho_*' instead of the ugly '_ho_*'. (0d11bc0)
* [relation] Raises a DeprecationWarning error if FKEYS is defined in a module. (b9a8622)
* [packager] Check if the connection file exists before proceeding. (17884cc)

## BREAKING CHANGE

`_ho_*` methods in half_orm.relation.Relation are replaced by `ho_*`

# 0.8.0 (2023-04-20)

* [doc] Add margin to hop_workflow png. (903c707)
* [doc] pg_meta. (3ff7c7b)
* [test] Add tests for deprecated and function and procedure. (2824622)
* [model] Remove Model._check_deja_vu_class method. (c3a1d0f)
* Add relation_factory module. (dd83534)
* [WIP] (d314414)
* [test] Delete all entries from  halftest.actor.person before starting the tests. (284a79a)
* [relation] Change SQL query formatting. (7ddc6f8)
* [WIP][refactor] Add trace decorator on DML methods. (b11d196)
* pylint... (ce6a55a)
* [WIP][refactor] SQL query formatting. (808909c)
* [WIP][refactor] Add method Relation.__fkey_where. (a0b74a0)
* [WIP][refactor] Rename method Relation.__what_to_insert to Relation.__what (f05887b)
* Rename Fkey._prep_select to Fkey._fkey_prep_select. (c153df9)
* [doc] Add png image. (4d37313)
* [doc] background white for hop_workflow.svg. (14d576b)
* Fix hop mini-doc URL. Add a white background to the workflow image. (d970491)
* [WIP][doc] Add a mini-documenation for the hop command. (07091db)
* Revert "[relation] Rewrite _ho_is_empty." (786aec2)
* [relation] Rewrite _ho_is_empty. (8bc38f4)
* [test] Fkey. (22ea8a5)
* Remove unused and dead code. (cbf71ce)
* [test] Test class HoTestCase. (90b3831)
* [test] relation ioperators. (ea7bfa9)
* [test] Relation._ho_cast. (92a575c)
* [test] relation._ho_join. (30f8121)
* [relation] Add context manager for Relation objects. (4bd5c6e)
* [test] _ho_limit, _ho_offset, _ho_dict & _ho_only. (9b28577)
* [test] Set operators on foreign keys. (95b21ab)
* [test] _ho_join errors. (c5d11b2)
* [relation] _ho_dict does not return not set values. Remove __join private method. (89aea1f)
* [test] Relation repr. (6570e32)
* [relation] Mark _ho_group_by and _ho_json as not tested. (09aded8)
* [test] Check automatic reconnection after postgresql is restarted (uses sudo). (28cf326)

# 0.8.0rc11 (2023-03-18)

* [field] Fix Bad adapter for NULL. (2f07867)

# 0.8.0rc10 (2023-03-17)

* [hop] Check that we are on hop_main branch before upgrade in prod. (7702aed)
* [model] Remove psycopg2.pool. (c7d99e3)
* [test] More coverage. (9d66be0)
* [test] Coverage (without half_orm/packager) still pre-alpha. (78edfd1)

# 0.8.0rc9 (2023-03-06)

* [CI][github] Test on push/pull request on default branch. (49e5db2)
* [relation] Relation methods are now prefixed with '_ho_'. (5e981f8)
* [test] Reenable fkeys test_runtime_error. (81a9446)
* [CI] Only set git user.email and user.name if in Github CI environment. (bc8aaee)
* [hop] Don't override global git user infos in dummy_test.py. (b8fc5cc)

# 0.8.0rc8 (2023-02-24)

* [Field] Register psycopg2 json adapter. (053d39e)
* [test] deprecated methods in relation. (7f96874)
* [gitlab][CI] Fix dependency. (3c6ad02)
* Add shields to README. (9446b35)
* [github][ci] OK. (b637929)
* [model] Fix annotation. (598570a)

# 0.8.0rc7 (2023-02-21)

* [model] Fix typo in deprecated message. (6b76f6e)

# 0.8.0rc6 (2023-02-16)

* [hop] Add release SQL files. (2a2b2d1)
* [relation] BREAKING CHANGE. Returning values must be specified except for ho_insert. (acf363e)
* [pipenv] Add pylint. (github/master) (035a589)
* [model] Config file load error management. (be281e9)
* [model] Fix deprecation warning on Python interpretor call. (30adfcc)

# 0.8.0rc5 (2023-02-08)

* Bump cryptography from 39.0.0 to 39.0.1 (5d5c200)
* [model] Add connection pool. (71f96fd)
* [model] Refactor. (274318c)
* [hop] Test script. (b85422c)
* [hop][WIP] Rename command test-release to apply-release. (71fdada)
* [hop][WIP] Use pytest as a module. (github/master) (69b0c55)
* [CI] Add superuser to root role (postgresql). (1f73a97)

# 0.8.0rc4 (2023-01-25)

* [hop][WIP] Add --devel option to hop new. (03b4750)
* [hop][halftest] Update to latest hop release. (cb73fb9)
* Fix a spelling mistake with below. (6659943)
* Remove pytest requirement from setup.py. (5ef9a13)
* [hop] Add git origin in .hop/config (a remote is no longer mandatory.) (0efe5d0)
* [relation] Prefix protected attributes of class Relation with _ho. (269f3e9)
* Add context information for deprectated methods. (9869e9b)

# 0.8.0rc3 (2023-01-20)

* [hop][WIP] Add pytest dependency (replace with unittest ?). (bdd52e8)
* Rename public and protected methods of half_orm.relation.Relation. (81c1084)

# 0.8.0rc2, hop 0.1.0a1 (2023-01-16)

* [hop][WIP] Integration of the hop command into half_orm. (d801ba5)

NOTE.
The hop command is a work in progress. It will replace the half_orm_packager package.

# 0.8.0rc1 (2023-01-04)

* [Fix] Foreign keys aliases were wrongly set as class attributes. (1de3c07)
* (relation) Remove code used to manage obsolete FKEYS variable. (393fccc)
* Upgrade dependencies. (ba1a202)

# 0.8.0rc0 (2022-12-07)

* Remove dependencies to pydash, click and gitpython (moved to half_orm_packager). (501549f)
* [field] Allow json and jsonb columns to receive python jsonifiable objects. (8da564f)
* Remove unnecessary select(). (d7b7722)
* (test) join. Add test_join_with_joined_object_with_FKEYS. (17948a8)
* (BREAKING CHANGE)(relation) Relation FKEYS module variable support is now removed (use Fkeys class attribute instead). (6ea7bd2)
* (BREAKING CHANGE)(relation) Relation.insert now returns a dict. (dffd6e3)
* [ci] Add Python 3.11. (origin/master, origin/HEAD, master) (72efc57)

## Breaking changes

* The `FKEYS` module variable is no longer supported. It is now replaced by the `Fkeys` class attribute.
* `Relation.insert` method only inserts one row and was returning a dict in a list. It now returns directly the dict:

  Before:
  ```py
  row_dict = MyTable(a='Something').insert()[0]
  ```
  Now:
  ```py
  row_dict = MyTable(a='Something').insert()
  ```

# 0.7.4 (2022-10-10)

* [relation] Add returning values to insert, update and delete. (816ae18)
* [relation] Return dict instead of RealDictRow. (fcbcbe0)
* [relation] Relation objects are now iterators. (143f0b0)
* Add half_orm.__version__. (60521cf)

# 0.7.3 (2022-09-21)

* [field][fix] Unsetting a Field by assigning None to it did not work anymore. (ef0735c)

# 0.7.2 (2022-09-21)

* Do not include partitioned tables in pg_meta. (04f6637)
* [doc][WIP] Add documentation in model and relation modules. (2040c95)
* [model] move relation class factory from relation to model. (eee6d05)
* [relation] Remove count method. (f3577c1)
* [model] get_relation_class raises MissingSchemaInName. (b3c9702)
* [model] Remove unused parameters dbname and raise_error from Model constructor. (95a3153)
* [docs][pg_meta][field][model][BREAKING CHANGE] Privatize some public methods. (a756443)

# 0.7.1 (2022-09-05)

* [relation] Allow fields names to be passed to Relation.get method. (93caa77)
* Add Model.execute_function and Model.call_procedure methods. (35215b3)
* Switch development status to beta. (74d3c67)
* [test] Don't reuse instances of Relation objects in tests. (0e137ce)
* [repr] Fix duplicates in unique constraints. Update README. (a91678e)

## New features

* You can now trigger the execution of PostgreSQL stored procedures and
functions by using `Model.execute_fonction` and `Model.call_procedure` methods.
* You can now pass fields names to The `Relation.get` method:
  ```py
  gaston = Person(last_name='Lagaffe', first_name='Gaston').get('id')
  ```

# 0.7.0 (2022-08-22)

* Fix Relation constraints representation. (c7beac7)
* Add deprecation warning for FKEYS module variable. (286a84c)
* [test] half_orm.hotest.hotAssertIsUnique takes a list of fields names. (283aefd)

## Breaking change

The `FKEYS` module variable (undocumented, mainly used with half_orm_packager) is
deprecated. It is replaced by the `Fkeys` Relation class attribute.

# 0.7.0-rc0 (2022-07-12)

* [doc] Improve README. (3363818)
* [WIP][fkeys] Make fkeys chaining possible. (62bf465)
* [fkeys][documentation] Add info about Fkeys class attribute in the relation class documentation. (0bc5af7)
* [WIP] Switch FKEYS module variable to Fkeys class attribute in halftest package (hop next release). (fb15769)
* [WIP] Allow constraint in joined objects. (61cd3f6)
* [test] Add tests for Relation._schemaname and Relation._relationname. (6845941)
* [relation][WIP] take into account the Fkeys attribute for a class inheriting from get_relation_class (00ecffe)
* [meta] Use tuple instead of normalized fqrn for key in metadata. (347fd98)

# 0.6.4 (2022-05-18)

* Use pg_meta qrn manipluation fonctions in relation and fkey modules. (45c9836)
* [test] Test Model._reload. (99f7c64)
* [model][meta] Move qrn manipulation fonctions to pg_meta. (29def79)
* [meta] Rename pg_metaview to pg_meta. (558d328)
* [meta] Remove Model._metadata attribute. (f2a68b3)

## Note

This release fixes some problems with half_orm_packager (pre-alpha).

# 0.6.3 (2022-05-17)

* [Fix] Regression in 0.6.2: dotted schema names were not handled properly. (0830a0c)

# 0.6.2 (2022-05-17) DO-NOT-USE

* [Fkeys] Fix insert, update and delete with constraints defined through foreign keys. (7bf9c77)
* [META] Change keys and fqrn to "<db>":"<schema>"."<relation>" (eada1b3)
* [CI] Build stage (4d836f2)
* [CI] Test from python 3.6 to 3.10 (ff3db37)

# 0.6.1 (2022-05-04)

* [Transaction] Fix #6. Autocommit mode stays at False on rollback. (643f500)

## Breaking change

There is a bug in the previous versions of the Transaction class.
If you use the Transaction class, **please upgrade to this release**.

# 0.5.14 (2022-05-04)

* [Transaction] Fix #6. Autocommit mode stays at False on rollback. (643f500)

## Breaking change

There is a bug in the previous versions of the Transaction class.
If you use the Transaction class, **please upgrade to this release**.

# 0.6.0 (2022-04-28)

* [Breaking change] Relation.join. (fdb4be8)
* [WIP] join on reverse fkeys. (73c3233)

## Breaking change

`Relation.join` now accepts either a string or a list of strings.

```
lagaffe.join((Post(), 'posts', ['id']))
```

now returns `[{'id': value1}, {'id': value2}, ...]` instead of `[value1, value2, ...]`. It must be replaced by:

```
lagaffe.join((Post(), 'posts', 'id'))
```

# 0.5.13 (2022-03-30)
* Fix singleton decorator (97dec7e)

# 0.5.12 (2022-03-30)
* Fix #4. Allow args for singleton decorator. (3a3085c)
* fix config file import when HALFORM_CONF_DIR is not absolute (0c54c10)

# 0.5.11 (2022-02-11)
* Add singleton decorator. (9b643cf)
* README: replace . (d075977)

# 0.5.10 (2022-02-08)
* [doc] Add return value on insert. (6a70c56)
* Add warning when trying to call a Field. (86243da)
* [CI] .gitlab-ci.yml. test stage. (364b823)
* Replace format with f strings. (c45463b)

# 0.5.9. (2021-12-01)
* Quote columns names in SQL update. (7056b98)

# 0.5.8. (2021-10-12)
* [model] Add attribute production. (6046432)

# 0.5.7 (2021-09-28)
* [relation] join: only format to string instances of classes listed in TO_PROCESS. (cc81112)
* [relation] join method now raises an exception if the relations are not connected. (9152506)

# 0.5.6. (2021-09-22)
* [relation] join method. (4dd6286)

# 0.5.5 (2021-09-07)
* Add Model.diconnect method. (70af38e)

# 0.5.4 (2021-09-04)
* Add support for partitioned tables. (9106143)
* [relation] _mogrify now triggers the print of the SQL query when a DML method is invoked. (0e66601)
* Add Relation.is_empty method (faster than len(relation) == 0). (08ec57a)

# 0.5.3 (2021-09-01)
* README. (ee2d453)
* Add model.has_relation method. (9490482)

# 0.5.2 (2021-08-26)
* [test] Add HoTest class (model testing). (319ddc2)
* [doc] README. (3b9dea1)

# 0.5.1 Fix wrong url in setup. (2021-07-27)

# 0.5.0 (2021-07-27)
* Remove dependency to .hop/config. (ebe7e71)
* Removal of hop (see halfORM_packager). (7311505)
* [test] Remove nose dependency. Add pytest (13226ea)

# 0.4.7 (2021-07-19)
* [hop][0.0.2] Adds placeholder for class attributes. (bbf2990)
* [module_template_1] Fix typo. (f1466ed)
* [pylint] Remove useless parameters in super. (882a795)
* [hop][pylint] Ignore invalid-name and attribute-defined-outside-init. (10ed373)
* [hop] Remove useless encoding in module_template_1. Put hop release in the first line. (8ab9b14)
* [hop] Fix No space allowed after bracket pylint(bad-whitespace). (bae786b)
* [fkey] Use a sorted list in repr for the referenced columns of a foreign key. (21024cd)

# 0.4.6 (2021-07-08)
* [fkey] Add missing quotes in fields names. (2ff4f5d)
* [test] Replace FKEYS_PROPERTIES by FKEYS (e09ac10). (3c0a6a0)

# 0.4.5 (2021-06-22)
* [hop] hop update - fix warning message in generated files (c048cda)
* [hop] Fix local variable 'model' referenced before assignment. (09ee493)
* [hop] Add hop release in modules. Fix missing warning. (5976ddb)
* [init] if project config does not exist, asks for config creation (6132158)
* [model] Model can be instantiated even if there's no ".hop/config" file, (a1e3cf6)
* [hop][create] fix case when config file already exists but db is not yet created (59bc901)
* [hop][create] Fix ident login (7866b25)
* [hop][breaking] Replace "argparse" with "click". We now use "commands" instead of options : (6a3729f)
* [model] Remove default value for "config_file" (seems to be used all the time) (e8103b5)
* [scripts] set script to half_orm.hop.__init__:main (more precise than before) (b7bbc83)
* [setup.py] set __version__ in half_orm/__init__.py (to use it in hop -v) (a622abc)
* [deps] add click dependency (91684a3)
* [deps] missing dependency : pyYaml (f30cbbf)
* [pipfile] fix deps psycopg2 (fe2bba2)
* [patch][wip] Add missing penultimate_release view. (503816a)
* [patch] Ignore path with uppercase in first letter. (9989913)
* [fix] order in meta.view.last_release (6826178)
* [hop] Add init patch system. (e45e4f4)
* [hop] Skip camel case directories. (f186f06)


# 0.4.4 (2021-05-20)
* [hop][test] Fix wrong reference to package. (2a6a222)
* [hop] Adds a base_test module to the package. (5a27678)
* [hop] Fix error on create. (be4d3ff)

# 0.4.3 (2021-05-11)
* [hop] Add -i argument (ignore-tests) (6559244)
* [hop] Add basic testing. (14db2a0)

# 0.4.2 (2021-05-10)
* [hop/fkeys] Fix missing comma. FKEYS_PROPERTIES is deprecated. Ignore empty strings. (e09ac10)

# 0.4.1 (2021-05-10)
* [hop] Add FKEYS_PROPERTIES template. (131b529)
* Update license/setup. (aaa86dd)
* [hop/patch] Adds Patch class. (e95ca0f)
* [0.4.0] adding Pipfile to the hop package. (95dedf1)
* [setup] Fix missing hop package. (57111e1)
* [hop] Add release number to First release. (dc1056e)
* [Pipfile] Add coverage dev dependency. (2df7273)
* [hop] remove dead code. (c0420dd)
* [hop] Creates connection config file and database if missing. (5327ec3)
* [hop] Adds main/master and devel branches on create. (6a6b4e4)
* [hop] Generates skeleton test files. (b002cc8)
* [hop] Add date to meta.release. (9927a29)
* [hop] Add git project on init. (9f39516)
* [hop] Add patch system to hop. (b24ffd6)
* [0.3.1] new release. (9db30db)
* [template] setup.py README.rst -> README.md. (d7a8c69)
* [wip] Add patch system to the hop command. (0734f5d)
* [hop] Take into account HALFORM_CONF_DIR env variable. (49593e0)
* [relation] Remove None values from update kwargs. (8652909)
* Update CHANGELOG. (ef392a7)

# 0.3 (2020-11-15)

## Features

* Automatic attempt to reconnect to DB in case of execution failure. (2fd8f6d)
* Allow connection with only the database name. (325f712)
* Add HALFORM_CONF_DIR environment variable (defaults to /etc/half_orm). (45e3431)
* Prevent update and test package when creating the package with hop -c. (153cbf6)
* Allow None as a legit value to unset a field. (eb13677)
* hop renames README.rst to README.md and .haflORM to .hop. (307591c)
* Add usage information into the README file generated by hop. (c956339)
* Improve README in the package generated by hop. (00c3743)

## Fixes

* relation.is_set must always retrun a boolean. (942da6c)
* Typos in README. (0caba1c)
* Fix broken unaccent in relation. (9c3d910)

## Breaking Changes

* hop now generates a .hop directory in the package instead of .halfORM. (588c2bf)

# 0.2 (2020-04-29)

## Features

- Columns of a relation are now regular attributs of the Relation class.
  This is a breaking change.
- no more need to install halftest package (pip3) to test half_orm.
- with context on a relation now enters a transaction.

## Bug fixes

- allow weird column names: `a = 1` is a regular column name in PostgreSQL.
  Of course, you can't use the doted notation to handle such column with
  half_orm. Instead, use `rel.__dict__['a = 1']`.
- reverse fkeys

## Breaking Changes

- Relation class is not inheriting from OrderedDict anymore.
  If `rel` is a Relation object, `rel['col']` must be replaced by `rel.col`.
- A Relation object `rel` is frozen after initialisation (`__init__`),
  meaning you can't add attributes to it. This is to prevent errors due
  to typos in the expression `rel.col = 'a'` vs. `rel.cal = 'a'`. If
  `cal` column doesn't exist in the relation, an exception is raised.
  If you need to add an attribute to a class inheriting from Relation,
  you can use `_ho_unfreeze` and `_ho_freeze` methods.

# 0.1.0-alpha.7 (2016-11-29)

## Features

- **relation:** Inherit foreign keys. (acb51ba)
- **test:** Add halftest package. (f2d91af)
- **model, relation:** Add reverse foreign keys. (50edf5f)
- **relation:** cast method now returns the casted relation. (bbde48a)
- **relation:** Add order_by select parameter. (57791c7)

## Bug fixes

- **fkeys:** Use issubclass instead of hasattr. (2aaf58e)
- **relation, fkey:** Fix relations with multiple foreign keys. (1a69e16)

# 0.1.0-alpha.6 (2016-11-25)

## Bug fixes

- **relation:** Refactoring. Fix fkeys on relation with set operations. Need tests. (bd806f3)
- **relation:** Check if right obj is None in \_\_set__op__. (4cf0b6a)
- **relation:** \_\_neg__ now uses \_\_set__op__ method. (444763c)
- **relation:** Pass the comparison operator with the value in to_dict method. (67e8724)
- **test:** Universe and empty sets are now correctly defined (1 = 1 patch). (2babe1f)

# 0.1.0-alpha.5 (2016-11-22)

## Features

- **halfORM:** Catch error if there is some wierd inheritance in PG that Python MRO can't handle. (aa9543e)
- **field:** Replace \_set_value method by set.
- **relation:** The ugly yet very useful 1 = 1 patch. (fd3d06f)
- **fkey:** Refactoring. Reverse key is now named after the relation it references. (5b98194)

## Bug fixes

- **relation:** Disambiguation of column name when using SQL join request.Disambiguation of column name when using SQL join request. (25f9a48)
- **halfORM:** Fix typo in module_template_1. (664159b)
- **relation:** Fix bug with FKEYS_PROPERTIES and inheritance. (675171f)
- **relation:** count must use distinct. (d6ac16b)
- **relation:** Fix joins with set operators. (e4c885c)

# 0.1.0-alpha.4 (2016-11-14)

## Features

- **halfORM:** Reduce to two the spaces reserved to the developper in relation modules (85c3d6c, 0cd6d5f)
- **model:** raise_error parameter is now passed to \_connect/reconnect. (6bba6dd)
- **relation:** Add attribute \_qrn (<schema name>.<relation name>) without double quotes. (fd6c07d)
- **relation:** Add \_set_fkeys_properties. (2b0335f)

## Bug fixes

- **halfORM:** Reverse the order in inheritance. (d7d4432)
- **halfORM:** Use aliases for imported inherited classes. Add warning in every modules. (e1f9841)

# 0.1.0-alpha.3 (2016-11-12)

## Features

- **Relation:** Add a cast method to cast to another relation type. (d662ccd)
- **halfORM:** The script can now be called without argument inside a half_orm package. (95a4ba0)
- **Model:** Model.relation replaced by get_relation_class now returns a class. (0998253)
- **Relation:** \_\_str__ becomes \_\_repr__. (af6498b)

## Bug fixes

- **halfORM:** Fix problem with curly braces in user's code. (7a02309)
- **Fkey:** The FK now references the class in the good scope. (fc304c7)
- **Relation:** Use field.where_repr to have a correct construct of the request with fkeys. (39116a2)
- **Relation:** remove the display of FOREIGN KEY when there is no FK. (89d9c6b)

# 0.1.0-alpha.2 (2016-11-10)

## Features

- **Fkey:** Add tests for foreign keys. (5158ece)
- **Relation:** attributes fields and fkeys are renamed \_fields and \_fkeys. (2e29af0)
- **Relation:** mogrify is renamed to \_mogrify. (3f3541f)

## Bug fixes

- **Fkey:** Fix bug in fkey introduced in 3c248a29 by fqrn renaming. (5158ece)
- **Fkey:** Fix is_set pb with fkeys and not constrained relations. (1c6e7d9)
- **Relation:** len wasn't working since Fields introduction. (2e29af0)
- **Relation:** Fix pb with isinstance and Relation objects. (51ff1db)

# 0.1.0-alpha.1 (2016-11-08)

- First alpha release
