"""Migration support for halfORM extensions.

Extensions (e.g. half-orm-dev) use :func:`get_breaking_changes_dir` to locate
the ``BREAKING_CHANGES-X.Y.Z.md`` files shipped with this package and display
relevant migration notes when the user upgrades through a breaking version.
"""

from pathlib import Path


def get_breaking_changes_dir() -> Path:
    """Return the directory containing ``BREAKING_CHANGES-X.Y.Z.md`` files.

    The returned path always points to the ``migrations/`` directory inside
    the installed ``half_orm`` package, regardless of the installation method
    (regular install, editable install, virtual environment, etc.).

    Returns:
        Path: an existing directory; never ``None``.

    Example (in an extension)::

        try:
            from half_orm.migrations import get_breaking_changes_dir
            half_orm_migrations = get_breaking_changes_dir()
        except (ImportError, AttributeError):
            half_orm_migrations = None   # older half-orm — ignore silently
    """
    return Path(__file__).parent