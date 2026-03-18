#-*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods

"""The null module provides the Null class
The Null class is used to set NULL value to relation fields.
"""

from psycopg.adapt import Dumper

__all__ = ['NULL']

class Null:
    """The Null class"""

class NullDumper(Dumper):
    """Dumper for the Null class — renders as SQL NULL literal."""
    def dump(self, obj):
        return b"NULL"

    def quote(self, obj):
        return b"NULL"

NULL = Null()
