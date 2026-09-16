# Breaking changes

For each release that requires a change in your code, halfORM ships a note
saying what changed and what to write instead. Those notes live inside the
installed package, in `half_orm/migrations/`, where upgrade tooling reads them
through
[`get_breaking_changes_dir()`](extensions/breaking-changes-api.md) — so what
you read here and what `half_orm dev` shows you before an upgrade are the same
text, not two copies of it.

For everything else in a release — fixes, additions, behaviour changes that do
not break an API — see the
[CHANGELOG](https://github.com/half-orm/half-orm/blob/main/CHANGELOG.md).

## Coming from a release before 1.0

**Every version before 1.0.0 was published as Beta**
(`Development Status :: 4 - Beta`), and the 0.18 line still carries that
classifier. 1.0.0 was the first release declared Production/Stable; **1.1.0 is
the current stable release, and the one to be on.**

If you are still on 0.x, the upgrade is worth planning rather than postponing:

- Read the 1.0.0 notes below. The jump crosses them, and they are the changes
  that will not happen silently.
- Read the [CHANGELOG](https://github.com/half-orm/half-orm/blob/main/CHANGELOG.md)
  for 1.1.0, which describes several behaviour changes that break nothing at
  the API level but change what your code does — a configuration file saying
  `production = false` was being read as *true*, for one.
- Know what you keep by staying: the 0.18 line is in maintenance and received
  only part of the 1.1 security work. What it did not receive is listed in the
  [0.18 advisory](security-0.18.md), and `order_by` is on that list.

<!-- breaking-changes -->
