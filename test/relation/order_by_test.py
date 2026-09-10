#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""order_by, limit and offset are interpolated into the query rather than
bound as parameters, so ho_select checks them before rendering.

Both routes into the query builder are covered: the plain one and the
json_agg one, which used to bypass these checks entirely."""

from unittest import TestCase

from half_orm import relation_errors
from half_orm.relation import _ho_parse_order_by

from ..init import halftest


class TestParseOrderBy(TestCase):
    "Unit tests for the clause parser."

    COLUMNS = ('last_name', 'first_name', 'birth_date')

    def parse(self, order_by):
        return _ho_parse_order_by(order_by, self.COLUMNS)

    def test_plain_column(self):
        self.assertEqual(self.parse('last_name'), '"last_name"')

    def test_direction(self):
        self.assertEqual(self.parse('last_name desc'), '"last_name" desc')
        self.assertEqual(self.parse('last_name ASC'), '"last_name" asc')

    def test_several_terms(self):
        self.assertEqual(
            self.parse('last_name, first_name desc'),
            '"last_name", "first_name" desc')

    def test_nulls_placement(self):
        self.assertEqual(
            self.parse('birth_date desc nulls last'),
            '"birth_date" desc nulls last')

    def test_quoted_column(self):
        self.assertEqual(self.parse('"last_name"'), '"last_name"')

    def test_ordinal(self):
        "ordering by output column number carries no identifier at all"
        self.assertEqual(self.parse('1 desc'), '1 desc')

    def test_unknown_column_rejected(self):
        with self.assertRaises(relation_errors.UnknownAttributeError):
            self.parse('no_such_column')

    def test_injection_rejected(self):
        for order_by in (
                '1; drop table actor.person',
                'last_name; select 1',
                '(select 1)',
                'lower(last_name)',
                'r1.last_name',
                'last_name --',
                "last_name' or '1'='1",
                'last_name desc, (select version())',
        ):
            with self.assertRaises((ValueError, relation_errors.UnknownAttributeError),
                                   msg=f'accepted: {order_by!r}'):
                self.parse(order_by)

    def test_non_string_rejected(self):
        for order_by in (1, ['last_name'], object()):
            with self.assertRaises(ValueError):
                self.parse(order_by)

    def test_trailing_comma_rejected(self):
        with self.assertRaises(ValueError):
            self.parse('last_name,')


class TestSelectParams(TestCase):
    "The checks must apply identically with and without json_agg."

    def setUp(self):
        self.person = halftest.person_cls
        self.post = halftest.post_cls

    def _with_json_agg(self):
        p = self.person(last_name=('like', 'a%'))
        p.post_rfk.set(self.post())
        return p

    # -- plain path ----------------------------------------------------

    def test_order_by_injection_rejected(self):
        with self.assertRaises(ValueError):
            list(self.person().ho_select(order_by='1; -- '))

    def test_limit_must_be_int(self):
        with self.assertRaises(ValueError):
            list(self.person().ho_select(limit='1'))

    def test_limit_rejects_bool(self):
        "bool is an int in Python, but 'limit True' is not SQL"
        with self.assertRaises(ValueError):
            list(self.person().ho_select(limit=True))

    def test_offset_must_be_int(self):
        with self.assertRaises(ValueError):
            list(self.person().ho_select(offset='0; --'))

    # -- json_agg path -------------------------------------------------

    def test_order_by_injection_rejected_with_json_agg(self):
        with self.assertRaises(ValueError):
            list(self._with_json_agg().ho_select(
                order_by='1; --', json_agg={'post_rfk': ['title']}))

    def test_limit_must_be_int_with_json_agg(self):
        with self.assertRaises(ValueError):
            list(self._with_json_agg().ho_select(
                limit='1 --', json_agg={'post_rfk': ['title']}))

    def test_offset_must_be_int_with_json_agg(self):
        with self.assertRaises(ValueError):
            list(self._with_json_agg().ho_select(
                offset='0; --', json_agg={'post_rfk': ['title']}))

    def test_unknown_order_by_column_with_json_agg(self):
        with self.assertRaises(relation_errors.UnknownAttributeError):
            list(self._with_json_agg().ho_select(
                order_by='no_such_column', json_agg={'post_rfk': ['title']}))

    # -- documented forms keep working ---------------------------------

    def test_documented_forms_still_work(self):
        for order_by in ('last_name', 'last_name desc',
                         'last_name, first_name desc',
                         'last_name DESC NULLS LAST', '"last_name"', '1'):
            rows = list(self.person().ho_select(
                'last_name', 'first_name', order_by=order_by, limit=2))
            self.assertEqual(len(rows), 2, msg=f'order_by={order_by!r}')

    def test_ordering_is_actually_applied(self):
        asc = [r['last_name'] for r in self.person().ho_select(
            'last_name', order_by='last_name', limit=5)]
        desc = [r['last_name'] for r in self.person().ho_select(
            'last_name', order_by='last_name desc', limit=5)]
        self.assertEqual(asc, sorted(asc))
        self.assertNotEqual(asc, desc)
