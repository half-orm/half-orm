#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

import psycopg
from unittest import TestCase

from ..init import halftest
from half_orm import relation_errors, model

class Test(TestCase):
    def setUp(self):
        self.pers = halftest.relation("actor.person")
        self.post = halftest.relation("blog.post")

    def test_is_not_set(self):
        set_pers = self.pers(id=1)
        non_set_pers = set_pers()
        self.assertFalse(non_set_pers.ho_is_set())

    def test_is_set(self):
        set_pers = self.pers(id=1)
        self.assertTrue(set_pers.ho_is_set())

    def test_is_set_fkey(self):
        set_pers = self.pers(id=1)
        set_post = self.post()
        set_post.author_fk.set(set_pers)
        self.assertTrue(set_post.ho_is_set())

    def test_is_set_op_or_both_unconstrained(self):
        """A() | A() — both unconstrained → not set (union = all rows)."""
        self.assertFalse((self.pers() | self.pers()).ho_is_set())

    def test_is_set_op_or_one_unconstrained(self):
        """A() | A(id=1) — one unconstrained → not set (union = all rows)."""
        self.assertFalse((self.pers() | self.pers(id=1)).ho_is_set())

    def test_is_set_op_or_both_constrained(self):
        """A(id=1) | A(id=2) — both constrained → set."""
        self.assertTrue((self.pers(id=1) | self.pers(id=2)).ho_is_set())

    def test_is_set_op_and_both_unconstrained(self):
        """A() & A() — both unconstrained → not set."""
        self.assertFalse((self.pers() & self.pers()).ho_is_set())

    def test_is_set_op_and_one_constrained(self):
        """A() & A(id=1) — one constrained → set."""
        self.assertTrue((self.pers() & self.pers(id=1)).ho_is_set())

    def test_is_set_op_and_not_unconstrained_minus_constrained(self):
        """A() - A(id=1) → set (= all except id=1)."""
        self.assertTrue((self.pers() - self.pers(id=1)).ho_is_set())

    def test_is_set_op_composition(self):
        """(A() | x) & y → set when y is constrained (= y, because A()|x = all rows)."""
        a = self.pers()
        x = self.pers(id=1)
        y = self.pers(first_name='Alice')
        self.assertFalse((a | x).ho_is_set())
        self.assertTrue(((a | x) & y).ho_is_set())

    def test_non_set_net_is_non_set(self):
        pers = self.pers()
        set_pers = -pers
        self.assertTrue(set_pers.ho_is_set())
        self.assertFalse(pers.ho_is_set())
