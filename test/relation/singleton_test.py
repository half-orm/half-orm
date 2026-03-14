#!/usr/bin/env python
#-*- coding:  utf-8 -*-

from random import randint
import psycopg2
import sys
from unittest import TestCase
from datetime import date

from ..init import halftest
from half_orm import relation_errors, model
from half_orm.relation import singleton
from half_orm.relation_errors import NotASingletonError

def name(letter, integer):
    return f"{letter}{chr(ord('a') + integer)}"

class Test(TestCase):
    def setUp(self):
        self.pers = halftest.person_cls()
        self.post = halftest.post_cls()
        self.today = halftest.today
        self.blog_view_cls = halftest.blog_view_cls

    def test_singleton_ok(self):
        """name method is decorated with @singleton in halftest.actor.person.Person class"""
        aa = self.pers(last_name='aa', first_name='b', birth_date='1970-01-01')
        aa.ho_assert_is_singleton()
        aa.name()

    def test_not_a_singleton_partial_pk(self):
        """Should raise NotASingletonError when only part of the PK is set and no ukey matches"""
        aa = self.pers(first_name='aa')
        with self.assertRaises(NotASingletonError):
            aa.ho_assert_is_singleton()
        with self.assertRaises(NotASingletonError):
            aa.name()

    def test_not_a_singleton_raised_whole_set(self):
        """Should raise NotASingletonError on a view"""
        aa = self.blog_view_cls()
        with self.assertRaises(NotASingletonError):
            aa.ho_assert_is_singleton()

    def test_singleton_via_ukey_id(self):
        """person(id=42) is a singleton via unique NOT NULL constraint on id"""
        p = self.pers(id=42)
        p.ho_assert_is_singleton()

    def test_singleton_via_ukey_last_name(self):
        """person(last_name='aa') is a singleton via unique NOT NULL constraint on last_name"""
        p = self.pers(last_name='aa')
        p.ho_assert_is_singleton()

    def test_not_singleton_nullable_unique(self):
        """post(title=..., content=...) is NOT a singleton: (title, content) unique but nullable"""
        p = self.post(title='t', content='c')
        with self.assertRaises(NotASingletonError):
            p.ho_assert_is_singleton()

    def test_orig_args_attribute(self):
        "Test that a function decorated by @singleton has the attribute __orig_args and that it is a FullArgSpec object"
        self.assertTrue(hasattr(self.pers.name, '__orig_args'))
        expected = "FullArgSpec(args=['self', 'last_name'], varargs=None, varkw=None, defaults=(None,), kwonlyargs=[], kwonlydefaults=None, annotations={'last_name': <class 'str'>})"
        self.assertEqual(str(getattr(self.pers.name, '__orig_args')), expected)
