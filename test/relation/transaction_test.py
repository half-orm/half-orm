#!/usr/bin/env python
# -*- coding:  utf-8 -*-

import io
import contextlib

from unittest import TestCase
from psycopg2.errors import UniqueViolation
from half_orm.transaction import Transaction
from half_orm.relation import transaction

from ..init import halftest

DUP_ERR_MSG = """psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "person_first_name_key"
DETAIL:  Key (last_name)=(aa) already exists.

Rolling back!
"""

class Pers(halftest.person_cls):
    @transaction
    def unique_violation(self):
        for name in ['abc', 'abd', 'aa']:
            self(first_name=name[0], last_name=name, birth_date='1970-01-01').ho_insert()

class Test(TestCase):
    def setUp(self):
        self.pers = halftest.person_cls()
        self.post = halftest.post_cls()
        self.today = halftest.today
        self.f = io.StringIO()

    def tearDown(self):
        self.f.close()

    def test_transaction_rollback(self):
        "Should rollback with correct error"
        with contextlib.redirect_stderr(io.StringIO()) as f:
            self.assertRaises(UniqueViolation, Pers().unique_violation)
        # self.assertEqual(DUP_ERR_MSG, f.getvalue())
        self.assertEqual(60, self.pers.ho_count())

    def test_transaction_rollback_to_level_0(self):
        "Should rollback to level 0 if nested transcation"
        def error():
            def uniq_violation2(pers):
                self.assertEqual(Transaction(halftest.model).level, 2)
                for name in ['xbc', 'xbd']:
                    pers.__class__(
                        first_name=name, last_name=name, birth_date='1970-01-01').ho_insert()

            def uniq_violation1(pers):
                self.assertEqual(Transaction(halftest.model).level, 1)
                with Transaction(halftest.model):
                    uniq_violation2(pers)
                for name in ['abc', 'abd', 'aa']:
                    pers.__class__(
                        first_name=name, last_name=name, birth_date='1970-01-01').ho_insert()

            with Transaction(halftest.model):
                uniq_violation1(self.pers)

        with contextlib.redirect_stderr(self.f):
            self.assertRaises(UniqueViolation, error)
            # self.assertEqual(DUP_ERR_MSG, self.f.getvalue())
        self.assertEqual(Transaction(halftest.model).level, 0)
