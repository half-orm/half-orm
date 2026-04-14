"""This module provides the errors for the relation module."""

class ExpectedOneError(Exception):
    """Base exception raised by :meth:`~half_orm.relation.Relation.ho_get`
    when the predicate does not match exactly one row.

    Two concrete subclasses carry the specific cases:

    * :exc:`NotFoundError` — no row matched (count == 0).
    * :exc:`MultipleRowsError` — more than one row matched (count > 1).
    """


class NotFoundError(ExpectedOneError):
    """No row matched the predicate passed to
    :meth:`~half_orm.relation.Relation.ho_get`.
    """
    def __init__(self, relation):
        self.rel = relation
        self.count = 0
        super().__init__(f'{relation.__class__.__name__}: no row found')


class MultipleRowsError(ExpectedOneError):
    """More than one row matched the predicate passed to
    :meth:`~half_orm.relation.Relation.ho_get`.
    """
    def __init__(self, relation):
        self.rel = relation
        super().__init__(
            f'{relation.__class__.__name__}: expected 1 row, got more than one'
        )

class UnknownAttributeError(Exception):
    """Unknown attribute error"""
    def __init__(self, msg):
        super().__init__(f"ERROR! Unknown attribute: {msg}.")

class IsFrozenError(Exception):
    """Class is frozen"""
    def __init__(self, cls, msg):
        super().__init__(
            f"ERROR! The class {cls} is forzen.\n"
            f"Use ho_unfreeze to add the '{msg}' attribute to it.")

class DuplicateAttributeError(Exception):
    """Attempt to setattr to an already existing attribute."""

class NotASingletonError(Exception):
    """The constraint does not define a singleton.

    Raised when the primary key is not fully set with equality comparators.
    """
    def __init__(self, msg):
        Exception.__init__(self, f'Not a singleton. {msg}')

class ReadOnlyRelationError(Exception):
    """Raised when a write operation is attempted on a read-only relation (view, materialized view)."""
    def __init__(self, relation):
        super().__init__(
            f"'{relation.__class__.__name__}' is a {relation._ho_kind} and does not support "
            "write operations (ho_insert, ho_update, ho_delete).")

class WrongFkeyError(Exception):
    "Raised when Fkeys contains a wrong name"
    def __init__(self, cls, value):
        fkeys_list = "\n".join([f" - {fkey}" for fkey in cls._ho_fkeys.keys()])
        err = f"Can't find '{value}'!\n" \
            f"List of keys for {cls.__class__.__name__}:\n" \
            f"{fkeys_list}"
        super().__init__(err)
