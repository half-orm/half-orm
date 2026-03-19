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


class FieldDumper(Dumper):
    """Psycopg 3 Dumper for Field objects.

    Delegates serialization to the appropriate dumper for ``Field.value``.
    This handles the case where a Field object is passed directly as a query
    parameter (e.g. ``Relation(col=other_relation.col)``).
    """

    def upgrade(self, obj, format):
        v = obj.value
        if isinstance(v, Null) or v is None:
            return NullDumper(type(obj), self.connection)
        return self

    def dump(self, obj):
        v = obj.value
        if isinstance(v, Null) or v is None:
            return None
        from psycopg.adapt import Transformer, PyFormat
        tx = Transformer(self.connection)
        return tx.get_dumper(v, PyFormat.AUTO).dump(v)
