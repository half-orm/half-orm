#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for ho_list()."""

from unittest import TestCase

from ..init import halftest
from half_orm.relation import ho_list

class TestHoList(TestCase):
    def setUp(self):
        self.Person = halftest.relation("actor.person")

    # --- basic equivalence ---------------------------------------------------

    def test_two_elements_same_as_or(self):
        "ho_list(r1, r2) is equivalent to r1 | r2."
        r1 = self.Person(last_name='aa')
        r2 = self.Person(last_name='ab')
        self.assertEqual(ho_list(r1, r2).ho_count(), (r1 | r2).ho_count())

    def test_three_elements(self):
        "ho_list(r1, r2, r3) covers exactly three distinct rows."
        r1 = self.Person(last_name='aa')
        r2 = self.Person(last_name='ab')
        r3 = self.Person(last_name='ac')
        self.assertEqual(ho_list(r1, r2, r3).ho_count(), 3)

    def test_single_element(self):
        "ho_list with one element is equivalent to that element."
        r = self.Person(last_name='aa')
        self.assertEqual(ho_list(r).ho_count(), r.ho_count())

    # --- membership (in) -----------------------------------------------------

    def test_member_is_in(self):
        "A relation that matches a listed row is in the list."
        hl = ho_list(self.Person(last_name='aa'), self.Person(last_name='ab'))
        self.assertIn(self.Person(last_name='aa'), hl)

    def test_non_member_is_not_in(self):
        "A relation that matches an unlisted row is not in the list."
        hl = ho_list(self.Person(last_name='aa'), self.Person(last_name='ab'))
        self.assertNotIn(self.Person(last_name='ac'), hl)

    # --- ∅ ⊆ S (empty-set property) ------------------------------------------

    def test_empty_set_in_any_list(self):
        """∅ ⊆ S — a relation matching no rows is always 'in' any ho_list.

        ``__contains__`` computes ``(right - self).ho_count() == 0``.
        When *right* is ∅ (no rows), the subtraction is always empty,
        so the result is True regardless of the contents of the list.
        """
        hl = ho_list(self.Person(last_name='aa'), self.Person(last_name='ab'))
        non_existent = self.Person(last_name='zzz_does_not_exist')
        self.assertEqual(non_existent.ho_count(), 0)   # confirm ∅
        self.assertIn(non_existent, hl)

    def test_intersection_alternative_avoids_empty_set_trap(self):
        """not (r & ho_list(...)).ho_is_empty() returns False for ∅.

        Unlike ``r in ho_list(...)``, the intersection-based check does not
        suffer from the ∅ ⊆ S edge case: if *r* has no rows, the
        intersection is empty and ho_is_empty() correctly returns True.
        """
        hl = ho_list(self.Person(last_name='aa'), self.Person(last_name='ab'))
        non_existent = self.Person(last_name='zzz_does_not_exist')
        self.assertTrue((non_existent & hl).ho_is_empty())

    # --- unconstrained-operand trap ------------------------------------------

    def test_unconstrained_operand_always_true(self):
        "When list is unconstrained, every 'in' check returns True."
        hl = ho_list(self.Person(last_name='aa'), self.Person())
        self.assertIn(self.Person(last_name='ac'), hl)

    # --- type safety ---------------------------------------------------------

    def test_different_relations_raise_type_error(self):
        "Checking 'in' between different relation types raises TypeError."
        Post = halftest.relation("blog.post")
        with self.assertRaises(TypeError) as ctx:
            self.Person(last_name='aa') in Post(title='hello')
        self.assertIn('actor.person', str(ctx.exception))
        self.assertIn('blog.post', str(ctx.exception))

    # --- empty-args guard ----------------------------------------------------

    def test_empty_raises_value_error(self):
        with self.assertRaises(ValueError):
            ho_list()