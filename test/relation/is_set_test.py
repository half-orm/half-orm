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

    def test_is_set_op(self):
        non_set_pers = self.pers()
        set_pers = self.pers(id=1)
        non_set_pers |= set_pers()
        self.assertTrue(non_set_pers.ho_is_set())

    def test_non_set_net_is_non_set(self):
        pers = self.pers()
        set_pers = -pers
        self.assertTrue(set_pers.ho_is_set())
        self.assertFalse(pers.ho_is_set())
