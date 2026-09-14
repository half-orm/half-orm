#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for quoting and splitting qualified relation names.

PostgreSQL allows a quote in a relation name -- `create table "t""bl"` -- and
these names are interpolated into statements.
"""

from unittest import TestCase

from half_orm import pg_meta
from half_orm.model import _split_qualified_name
from half_orm import model_errors

from ..init import model


class TestQuoteIdent(TestCase):
    def test_an_ordinary_name(self):
        self.assertEqual(pg_meta.quote_ident('person'), '"person"')

    def test_a_quote_is_doubled(self):
        """Unescaped, it would close the identifier early."""
        self.assertEqual(pg_meta.quote_ident('t"bl'), '"t""bl"')

    def test_a_name_that_is_only_quotes(self):
        self.assertEqual(pg_meta.quote_ident('""'), '""""""')


class TestNormalize(TestCase):
    def test_qrn_drops_the_database(self):
        self.assertEqual(
            pg_meta.normalize_qrn(('halftest', 'actor', 'person')),
            '"actor"."person"')

    def test_qrn_escapes(self):
        self.assertEqual(
            pg_meta.normalize_qrn(('halftest', 'zz"q', 't"bl')),
            '"zz""q"."t""bl"')

    def test_fqrn_escapes(self):
        self.assertEqual(
            pg_meta.normalize_fqrn(('halftest', 'zz"q', 't"bl')),
            '"halftest":"zz""q"."t""bl"')


class TestSplitQualifiedName(TestCase):
    def test_bare(self):
        self.assertEqual(_split_qualified_name('blog.post'), ['blog', 'post'])

    def test_quoted(self):
        self.assertEqual(
            _split_qualified_name('"blog"."post"'), ['blog', 'post'])

    def test_an_escaped_quote_is_one_character(self):
        self.assertEqual(_split_qualified_name('"a""b"."t"'), ['a"b', 't'])

    def test_a_dot_inside_quotes_does_not_split(self):
        self.assertEqual(_split_qualified_name('"a.b"."c"'), ['a.b', 'c'])

    def test_a_name_outside_the_grammar(self):
        """The caller falls back on a plain split for these."""
        self.assertIsNone(_split_qualified_name('blog.a-b'))

    def test_an_unterminated_quote(self):
        self.assertIsNone(_split_qualified_name('"x'))


class TestNamesAreNotConflated(TestCase):
    """Two schemas differing only by a quote used to be the same name.

    `relation_name.replace('"', '')` deleted every quote before splitting, so
    a relation could be reached through a name that was not its own.
    """

    PLAIN = 'zzq_test'
    QUOTED = 'zz"q_test'

    @classmethod
    def setUpClass(cls):
        cls._drop()
        model.execute_query(f'create schema {cls.PLAIN}')
        model.execute_query(f'create table {cls.PLAIN}.t (id int)')
        model.execute_query(f'insert into {cls.PLAIN}.t values (1)')
        model.execute_query('create schema "zz""q_test"')
        model.execute_query('create table "zz""q_test"."t" (id int)')
        model.execute_query('insert into "zz""q_test"."t" values (2), (3)')
        model.reconnect(reload=True)

    @classmethod
    def tearDownClass(cls):
        cls._drop()
        model.reconnect(reload=True)

    @classmethod
    def _drop(cls):
        model.execute_query(f'drop schema if exists {cls.PLAIN} cascade')
        model.execute_query('drop schema if exists "zz""q_test" cascade')

    def test_the_plain_name_reaches_the_plain_schema(self):
        self.assertEqual(
            model.get_relation_class(f'{self.PLAIN}.t')().ho_count(), 1)

    def test_the_quoted_name_reaches_the_other_schema(self):
        self.assertEqual(
            model.get_relation_class('"zz""q_test"."t"')().ho_count(), 2)

    def test_an_unquoted_name_holding_a_quote_still_resolves(self):
        self.assertEqual(
            model.get_relation_class('zz"q_test.t')().ho_count(), 2)

    def test_the_generated_sql_quotes_the_name(self):
        cls = model.get_relation_class('"zz""q_test"."t"')
        self.assertEqual(cls._qrn, '"zz""q_test"."t"')

    def test_a_name_without_a_schema_is_still_refused(self):
        with self.assertRaises(model_errors.MissingSchemaInName):
            model.get_relation_class('person')
