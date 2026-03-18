#!/usr/bin/env python
#-*- coding:  utf-8 -*-

import sys
from unittest import TestCase
from random import randint
from datetime import date

import psycopg
from half_orm.transaction import Transaction

from ..init import model, halftest, GASTON

class Test(TestCase):
    def setUp(self):
        self.gaston = halftest.gaston
        self.gaston.ho_insert()
        self.ab = halftest.person_cls(last_name='a', first_name='b', birth_date='0001-01-01')
        self.post = halftest.post_cls()

    def tearDown(self):
        self.gaston.ho_delete()
        self.ab.ho_delete()

    def test_context(self):
        "context shout put the model in transaction mode"
        self.assertFalse(Transaction(halftest.model).is_set())
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with Transaction(halftest.model):
                self.ab.ho_insert()
                self.assertTrue(Transaction(halftest.model).is_set())
                self.gaston.ho_insert()
        self.assertEqual(self.ab.ho_count(), 0)
        self.assertFalse(Transaction(halftest.model).is_set())
