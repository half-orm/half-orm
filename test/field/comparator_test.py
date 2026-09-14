#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Comparators reach the WHERE clause as raw SQL, so Field.set() constrains
them to things that can only ever *be* an operator (see
`half_orm.field.check_comparator`)."""

from unittest import TestCase

from half_orm.field import Expr, check_comparator
from half_orm.null import NULL

from ..init import halftest


INJECTION = "= 'x' or 1=1 --"


class TestCheckComparator(TestCase):
    "Unit tests for the validator itself."

    def test_word_operators_accepted(self):
        for comp in ('in', 'not in', 'is', 'is not', 'like', 'not like',
                     'ilike', 'not ilike', 'similar to', 'not similar to',
                     'is distinct from', 'is not distinct from'):
            self.assertEqual(check_comparator(comp), comp)

    def test_word_operators_are_case_and_space_insensitive(self):
        self.assertEqual(check_comparator('IS NOT'), 'is not')
        self.assertEqual(check_comparator('  is   not  '), 'is not')
        self.assertEqual(check_comparator('NOT ILIKE'), 'not ilike')

    def test_symbolic_operators_accepted(self):
        "operators from extensions must keep working — they are not enumerated"
        for comp in ('=', '!=', '<>', '<', '<=', '>', '>=', '~', '~*', '!~',
                     '@@', '@>', '<@', '&&', '->>', '#>>', '%',
                     '<->',   # pgvector
                     '&&&'):  # PostGIS
            self.assertEqual(check_comparator(comp), comp)

    def test_injection_rejected(self):
        for comp in (INJECTION, "= 'x' or 1=1", "= any(select 1)", "or", "1=1"):
            with self.assertRaises(ValueError):
                check_comparator(comp)

    def test_comment_openers_rejected(self):
        "the operator character set can spell SQL comment openers"
        for comp in ('--', '=--', '/*', '=/*', '*/'):
            with self.assertRaises(ValueError):
                check_comparator(comp)

    def test_non_string_rejected(self):
        for comp in (42, None, ['='], ('=',)):
            with self.assertRaises(ValueError):
                check_comparator(comp)

    def test_error_message_names_the_offender(self):
        with self.assertRaises(ValueError) as ctx:
            check_comparator('drop table')
        self.assertIn('drop table', str(ctx.exception))


class TestFieldSetComparator(TestCase):
    """Field.set() has three ways to carry a comparator, and the Expr and
    Field branches return early — before the fix, only the first was
    (partially) constrained, and the other two reached the WHERE clause with
    no bound parameter at all."""

    def setUp(self):
        self.post = halftest.post_cls

    def test_injection_via_bound_value_rejected(self):
        with self.assertRaises(ValueError):
            self.post().title.set((INJECTION, 'x'))

    def test_injection_via_field_to_field_rejected(self):
        p = self.post()
        with self.assertRaises(ValueError):
            p.title.set((INJECTION, p.content))

    def test_injection_via_expr_rejected(self):
        with self.assertRaises(ValueError):
            self.post().title.set((INJECTION, Expr('"content"')))

    def test_valid_comparators_still_work(self):
        p = self.post(title=('like', 'a%'))
        self.assertTrue(p.title.is_set())
        self.assertIn('like', p._ho_prep_select()[0])

    def test_field_to_field_still_works(self):
        p = self.post()
        p.title.set(('>', p.content))
        query, _ = p._ho_prep_select()
        self.assertIn('>', query)
        self.assertIn('"content"', query)

    def test_expr_still_works(self):
        p = self.post()
        p.title.set(('>=', Expr('"content"')))
        self.assertIn('>=', p._ho_prep_select()[0])

    def test_null_comparator_unchanged(self):
        p = self.post()
        p.title.set(('is not', NULL))
        self.assertIn('is not', p._ho_prep_select()[0])
        with self.assertRaises(ValueError):
            self.post().title.set(('like', NULL))
