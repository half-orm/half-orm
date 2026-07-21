#!/usr/bin/env python3
#-*- coding: utf-8 -*-

"""Field's per-(operator, column type) RHS template — currently just
tsvector @@ plainto_tsquery(...), so a free-text search term (not
necessarily valid tsquery syntax) can be matched against a tsvector column
without callers having to know about the cast pitfall (see field.py's
_OPERATOR_RHS_TEMPLATES docstring).

Uses a synthetic Field (no DB round-trip needed: this is about the SQL
fragment field.py builds, not query execution) to avoid requiring a
tsvector column in the shared halftest schema.
"""

from unittest import TestCase

from half_orm.field import Field


class _FakeRelation:
    ho_id = 1


def _tsvector_field(name='search_vec'):
    metadata = {
        'fieldtype': 'tsvector', 'notnull': False, 'pkey': False,
        'fieldnum': 1, 'pkeynum': None, 'uniq': False,
        'fielddescription': None, 'default_expr': None,
    }
    return Field(name, _FakeRelation(), metadata)


class Test(TestCase):
    def test_where_repr_uses_plainto_tsquery(self):
        field = _tsvector_field()
        field.set(('@@', 'half orm search'))
        self.assertEqual(
            field._where_repr('', 1),
            '"search_vec" @@ plainto_tsquery(%s)',
        )

    def test_where_expr_uses_plainto_tsquery(self):
        field = _tsvector_field()
        field.set(('@@', 'half orm search'))
        expr = field._where_expr('', 1)
        sql, values = expr.to_sql()
        self.assertEqual(sql, '"search_vec" @@ plainto_tsquery(%s)')
        self.assertEqual(values, [field])

    def test_other_operator_on_tsvector_keeps_default_cast(self):
        """Only ('@@', 'tsvector') is overridden — anything else on a
        tsvector column still gets the default same-type cast."""
        field = _tsvector_field()
        field.set(('=', 'half orm search'))
        self.assertEqual(
            field._where_repr('', 1),
            '"search_vec" = %s::tsvector',
        )

    def test_at_at_on_non_tsvector_keeps_default_cast(self):
        """Only the (comp, sql_type) pair is overridden — @@ on some other
        column type falls back to the default cast, not plainto_tsquery."""
        metadata = {
            'fieldtype': 'jsonb', 'notnull': False, 'pkey': False,
            'fieldnum': 1, 'pkeynum': None, 'uniq': False,
            'fielddescription': None, 'default_expr': None,
        }
        field = Field('payload', _FakeRelation(), metadata)
        field.set(('@@', '{"a": 1}'))
        self.assertEqual(
            field._where_repr('', 1),
            '"payload" @@ %s::jsonb',
        )
