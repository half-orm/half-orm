# Breaking Changes API

halfORM ships a set of `BREAKING_CHANGES-X.Y.Z.md` files inside the installed
package. Extensions that manage upgrades (e.g.
[half-orm-dev](https://github.com/half-orm/half-orm-dev)) can read these files
to display relevant migration notes before asking the user to confirm an
upgrade.

---

## `half_orm.migrations.get_breaking_changes_dir()`

```python
from half_orm.migrations import get_breaking_changes_dir

directory = get_breaking_changes_dir()
# → Path('.../site-packages/half_orm/migrations')
```

Returns a `pathlib.Path` pointing to the directory that contains the
`BREAKING_CHANGES-X.Y.Z.md` files. The path is always valid after a standard
`pip install` (regular, editable, or virtual-environment install).

---

## File naming convention

| File | Applies to migrations whose target is |
|------|---------------------------------------|
| `BREAKING_CHANGES-1.0.0.md` | `>= 1.0.0` (includes `1.0.0rc1`, `1.0.0`, …) |
| `BREAKING_CHANGES-2.0.0.md` | `>= 2.0.0` |

Files are named after the **stable base version** of the series, not after the
first release candidate.  An extension must include a file for every version it
reads, filtering by whether the user's current version is strictly below that
base version.

---

## Integration pattern for extensions

```python
from packaging.version import Version

try:
    from half_orm.migrations import get_breaking_changes_dir
    _half_orm_migrations = get_breaking_changes_dir()
except (ImportError, AttributeError):
    _half_orm_migrations = None   # half-orm < 1.0.0 — no breaking-changes API


def get_half_orm_breaking_changes(current_version: str, target_version: str) -> str:
    """Return concatenated breaking-change notes for the given version range."""
    if _half_orm_migrations is None:
        return ""

    current = Version(current_version)
    target  = Version(target_version)
    notes   = []

    for path in sorted(_half_orm_migrations.glob("BREAKING_CHANGES-*.md")):
        base = Version(path.stem.replace("BREAKING_CHANGES-", ""))
        if current < base <= target:
            notes.append(path.read_text())

    return "\n\n".join(notes)
```

The `try/except (ImportError, AttributeError)` guard ensures the extension
works with older versions of halfORM that do not expose this API.