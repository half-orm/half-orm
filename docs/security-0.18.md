---
notice: "**0.18.14** backports part of the 1.1 security work to the 0.18 line. Several fixes are not in it, and will not be."
---

# Security advisory — 0.18

**Affected:** 0.18.13 and every release before it.
**Partly fixed in:** 0.18.14, released 2026-09-15.

The 0.18 line is in maintenance. It received a subset of the work described in
the [1.1 advisory](security-1.1.md), chosen for what could be backported
without changing behaviour the line's users depend on.

**1.x is where security work lands first, and in full.** If the choice is open
to you, upgrade rather than staying on 0.18.

It is also worth being plain about what 0.18 is: every release before 1.0.0 was
published as Beta (`Development Status :: 4 - Beta`), and this line still
carries that classifier. 1.1.0 is the current stable release. The upgrade
crosses 1.0.0, so read the [breaking changes](breaking-changes.md) and the
[CHANGELOG](https://github.com/half-orm/half-orm/blob/main/CHANGELOG.md) before
starting — that is the work this page is asking you to do, and it is smaller
than the list below.

## What 0.18.14 fixes

- The transaction that committed instead of rolling back when a Python
  exception escaped the block.
- `Field.set()` comparators, now validated before reaching the WHERE clause.
- Function and procedure names, and the keys of named parameters, checked
  before interpolation.
- `config_file` confined to its directory, and the reconnect guard extended to
  the branch that skipped it.
- `ho_copy()` and `ho_acopy()` column names checked against the relation.
- Relation names quoted properly, and no longer conflated with one another.
- The `eval()` in `hotest.py`, replaced by an attribute path walk.
- The CLI extension trust store moved out of the project directory, and
  `half-orm-test-extension` removed from the allowlist of automatically
  trusted names.
- Script injection through the documentation workflow's dispatch inputs.

## What it does not fix

These remain open on 0.18, and upgrading to 1.1 is the only remedy:

- **`order_by` and the `json_agg` projection** are still interpolated
  unchecked. If your application derives either from a request — a `?sort=`
  parameter, a field list from an API client — that path is exploitable, and it
  is the most reachable defect in this list.
- **`Model._import_class()`** still builds an import path from schema names
  read out of the database.
- **Query parameters** are still written to the log when a query fails.
- **Relation aliases** still carry `id(self)`, a heap address.
- **`ho_cast()`** still widens silently to an ancestor's whole extension.
- **The extension trust work beyond the store's location** — loading on first
  use rather than at import, checking that the module belongs to the
  distribution vouching for it, pinning approval to a digest of the code, and
  `HALF_ORM_TRUST_EXTENSIONS` for unattended runs — is 1.1 only. On 0.18,
  `--trusted-extensions` and `--untrust` are still parsed after the extensions
  have loaded.

## What to do if you must stay on 0.18

Upgrade to 0.18.14 first. Then, for what it does not cover:

- never build `order_by`, a `json_agg` projection or an alias from input you do
  not control — map the user's choice onto a name your own code holds;
- treat the database you connect to as trusted, since its schema names still
  select Python modules to import;
- do not rely on a failing query keeping its parameters out of your logs;
- approve CLI extensions deliberately, and re-check them after any reinstall.

## Credit

Found during an internal review of the 1.0.0 release, and backported from 1.1.0.
