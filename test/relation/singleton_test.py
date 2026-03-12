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

    def test_singleton_ok(self):
        """name method is decorated with @singleton in halftest.actor.person.Person class"""
        aa = self.pers(last_name='aa', first_name='b', birth_date='1970-01-01')
        aa.name()

    def test_not_a_singleton_raised_after_field_set(self):
        """Should raise NotASingletonError after setting a field on an OK singleton"""
        aa = self.pers(last_name='aa')
        with self.assertRaises(NotASingletonError):
            aa.name()

    def test_not_a_singleton_raised_whole_set(self):
        """Should raise NotASingletonError on whole set if it has more than one element"""
        aa = self.pers()
        with self.assertRaises(NotASingletonError):
            aa.name()

    def test_orig_args_attribute(self):
        "Test that a function decorated by @singleton has the attribute __orig_args and that it is a FullArgSpec object"
        self.assertTrue(hasattr(self.pers.name, '__orig_args'))
        expected = "FullArgSpec(args=['self', 'last_name'], varargs=None, varkw=None, defaults=(None,), kwonlyargs=[], kwonlydefaults=None, annotations={'last_name': <class 'str'>})"
        self.assertEqual(str(getattr(self.pers.name, '__orig_args')), expected)
