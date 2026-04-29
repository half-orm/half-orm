#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for Relation.ho_where_display."""

from unittest import TestCase

from ..init import halftest


class Test(TestCase):
    def setUp(self):
        self.pers = halftest.relation("actor.person")
        self.post = halftest.relation("blog.post")

    # --- unconstrained -------------------------------------------------------

    def test_unconstrained_returns_none(self):
        self.assertIsNone(self.pers().ho_where_display())

    # --- simple leaf ---------------------------------------------------------

    def test_simple_field_constraint(self):
        result = self.pers(first_name='Alice').ho_where_display()
        self.assertIsInstance(result, dict)
        self.assertNotIn('operator', result)
        self.assertIn('joins', result)
        self.assertIn('where', result)
        self.assertIn('values', result)
        self.assertIn('Alice', result['values'])

    def test_simple_fkey_join(self):
        post = self.post()
        post.author_fk.set(self.pers(first_name='Alice'))
        result = post.ho_where_display()
        self.assertIsInstance(result, dict)
        self.assertNotIn('operator', result)
        self.assertTrue(len(result['joins']) > 0)
        self.assertIn('Alice', result['values'])

    # --- compound set operations ---------------------------------------------

    def test_or_structure(self):
        result = (self.pers(first_name='Alice') | self.pers(first_name='Bob')).ho_where_display()
        self.assertEqual(result['operator'], 'or')
        self.assertIn('left', result)
        self.assertIn('right', result)
        self.assertIn('Alice', result['left']['values'])
        self.assertIn('Bob', result['right']['values'])

    def test_and_structure(self):
        result = (self.pers(first_name='Alice') & self.pers(last_name='Martin')).ho_where_display()
        self.assertEqual(result['operator'], 'and')
        self.assertIn('left', result)
        self.assertIn('right', result)

    def test_sub_structure(self):
        result = (self.pers() - self.pers(first_name='Alice')).ho_where_display()
        self.assertEqual(result['operator'], 'and not')
        self.assertIn('left', result)
        self.assertIn('right', result)

    def test_neg_simple_leaf_embedded_in_where(self):
        "Negation of a simple leaf: NOT (...) is embedded in the where string."
        result = (-self.pers(first_name='Alice')).ho_where_display()
        self.assertNotIn('operator', result)
        self.assertIn('not', result['where'])

    def test_neg_compound_structure(self):
        "Negation of a compound operation produces {'operator': 'neg', 'operand': ...}."
        compound = self.pers(first_name='Alice') | self.pers(first_name='Bob')
        result = (-compound).ho_where_display()
        self.assertEqual(result['operator'], 'neg')
        self.assertIn('operand', result)
        self.assertEqual(result['operand']['operator'], 'or')

    # --- nested --------------------------------------------------------------

    def test_nested_compound(self):
        a = self.pers(first_name='Alice')
        b = self.pers(first_name='Bob')
        c = self.pers(first_name='Carol')
        result = ((a | b) & c).ho_where_display()
        self.assertEqual(result['operator'], 'and')
        self.assertEqual(result['left']['operator'], 'or')
        self.assertNotIn('operator', result['right'])

    # --- or with one unconstrained branch → None -----------------------------

    def test_or_unconstrained_returns_none(self):
        "A() | A(id=1) is not set (union = all rows) → None."
        result = (self.pers() | self.pers(id=1)).ho_where_display()
        self.assertIsNone(result)