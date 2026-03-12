"""This module provides the errors for the relation module."""

class ExpectedOneError(Exception):
    """This exception is raised when get count differs from 1."""
    def __init__(self, relation, count):
        self.rel = relation
        self.count = count
        self.plural = '' if count == 0 else 's'
        Exception.__init__(self, f'Expected 1, got {self.count} tuple{self.plural}')

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

class WrongFkeyError(Exception):
    "Raised when Fkeys contains a wrong name"
    def __init__(self, cls, value):
        fkeys_list = "\n".join([f" - {fkey}" for fkey in cls._ho_fkeys.keys()])
        err = f"Can't find '{value}'!\n" \
            f"List of keys for {cls.__class__.__name__}:\n" \
            f"{fkeys_list}"
        super().__init__(err)
