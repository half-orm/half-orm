# Breaking changes

## Versioning

From 2.0.0, halfORM follows [Semantic Versioning](https://semver.org/):

- a **major** release (3.0.0) may require changes to your code, and comes
  with a note below saying what changed and what to write instead;
- a **minor** release (2.1.0) adds, and breaks nothing;
- a **patch** release (2.0.1) fixes, and breaks nothing.

One exception, and only one: a **security fix** may change a behaviour in a
minor or patch release, when that behaviour was the vulnerability. Each such
change is listed in the advisory that comes with the release and in the
[CHANGELOG](https://github.com/half-orm/half-orm/blob/main/CHANGELOG.md),
under *Behaviour changes*.

So `half_orm>=2.0,<3` is a safe requirement, and an extension built for 2.x
loads on any 2.x core.

Before 2.0.0 a minor release could break the API: 1.0, 1.1 and 1.2 each
changed behaviours an application could notice, and 2.0.0 is the release
that would have been 1.3.0.

## Notes

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
classifier. 1.0.0 was the first release declared Production/Stable.

If you are still on 0.x, the upgrade is worth planning rather than postponing:

- Read every note below, from 1.0.0 up. The jump crosses them all, and they
  are the changes that will not happen silently.
- Read the [CHANGELOG](https://github.com/half-orm/half-orm/blob/main/CHANGELOG.md)
  for 1.1.0 and 1.2.1, which describe behaviour changes that break nothing at
  the API level but change what your code does — a configuration file saying
  `production = false` was being read as *true*, for one.
- Know what you keep by staying: the 0.18 line is in maintenance and received
  only part of the 1.1 security work. What it did not receive is listed in the
  [0.18 advisory](security-0.18.md), and `order_by` is on that list.

<!-- breaking-changes -->
