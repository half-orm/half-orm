#!/usr/bin/env python
# -*- coding:  utf-8 -*-

import contextlib
import io

from unittest import TestCase

import psycopg

from half_orm.transaction import Transaction
from half_orm.relation import transaction

from ..init import halftest


class Test(TestCase):
    def setUp(self):
        self.model = halftest.model
        self.pers = halftest.person_cls()
        self.calls = []

    def tearDown(self):
        "No test may leave a frame of callbacks behind."
        self.assertEqual(0, Transaction(self.model).level)
        self.calls.clear()
        Transaction(self.model).after_commit(self.mark('left over'))
        self.assertEqual(['left over'], self.calls)

    def mark(self, tag):
        "A callback recording that it ran."
        return lambda: self.calls.append(tag)

    def boom(self):
        def callback():
            raise RuntimeError('callback failure')
        return callback

    def test_outside_a_transaction_the_callback_runs_at_once(self):
        "Nothing to wait for: the mutation commits on its own"
        Transaction(self.model).after_commit(self.mark('a'))
        self.assertEqual(['a'], self.calls)

    def test_outside_a_transaction_after_rollback_is_dropped(self):
        "Nothing can be undone any more"
        Transaction(self.model).after_rollback(self.mark('a'))
        self.assertEqual([], self.calls)

    def test_callback_runs_after_the_commit(self):
        with Transaction(self.model):
            Transaction(self.model).after_commit(self.mark('a'))
            self.assertEqual([], self.calls)
        self.assertEqual(['a'], self.calls)

    def test_callbacks_run_in_registration_order(self):
        with Transaction(self.model):
            for tag in 'abc':
                Transaction(self.model).after_commit(self.mark(tag))
        self.assertEqual(['a', 'b', 'c'], self.calls)

    def test_callback_sees_the_committed_rows(self):
        "What the callback announces must be readable by its audience"
        class Pers(halftest.person_cls):
            @transaction
            def add(self, calls):
                self(first_name='c', last_name='cbk', birth_date='1970-01-01').ho_insert()
                Transaction(self._ho_model).after_commit(
                    lambda: calls.append(self.__class__(last_name='cbk').ho_count()))

        try:
            Pers().add(self.calls)
            self.assertEqual([1], self.calls)
        finally:
            halftest.person_cls(last_name='cbk').ho_delete()

    def test_callback_runs_with_the_connection_back_in_autocommit(self):
        "A callback writing to the database must not reopen the transaction"
        with Transaction(self.model):
            Transaction(self.model).after_commit(
                lambda: self.calls.append(self.model._connection.autocommit))
        self.assertEqual([True], self.calls)

    def test_rollback_drops_the_commit_callbacks(self):
        with self.assertRaises(RuntimeError), Transaction(self.model):
            Transaction(self.model).after_commit(self.mark('commit'))
            Transaction(self.model).after_rollback(self.mark('rollback'))
            raise RuntimeError
        self.assertEqual(['rollback'], self.calls)

    def test_rollback_of_a_mutation_drops_its_callback(self):
        "End to end: no row, no event"
        with self.assertRaises(RuntimeError), Transaction(self.model):
            self.pers(
                first_name='c', last_name='cbk', birth_date='1970-01-01').ho_insert()
            Transaction(self.model).after_commit(self.mark('commit'))
            raise RuntimeError
        self.assertEqual([], self.calls)
        self.assertTrue(halftest.person_cls(last_name='cbk').ho_is_empty())

    def test_savepoint_rollback_drops_only_its_own_callbacks(self):
        with Transaction(self.model):
            Transaction(self.model).after_commit(self.mark('outer'))
            with self.assertRaises(RuntimeError), Transaction(self.model):
                Transaction(self.model).after_commit(self.mark('inner'))
                Transaction(self.model).after_rollback(self.mark('inner undone'))
                raise RuntimeError
            # The savepoint is settled as soon as it is rolled back.
            self.assertEqual(['inner undone'], self.calls)
        self.assertEqual(['inner undone', 'outer'], self.calls)

    def test_released_savepoint_hands_its_callbacks_to_the_enclosing_scope(self):
        with Transaction(self.model):
            with Transaction(self.model):
                Transaction(self.model).after_commit(self.mark('inner'))
                self.assertEqual([], self.calls)
            Transaction(self.model).after_commit(self.mark('outer'))
            self.assertEqual([], self.calls)
        self.assertEqual(['inner', 'outer'], self.calls)

    def test_released_savepoint_follows_the_enclosing_rollback(self):
        "A released savepoint is not committed: the outermost block decides"
        with self.assertRaises(RuntimeError), Transaction(self.model):
            with Transaction(self.model):
                Transaction(self.model).after_commit(self.mark('inner'))
                Transaction(self.model).after_rollback(self.mark('inner undone'))
            raise RuntimeError
        self.assertEqual(['inner undone'], self.calls)

    def test_a_failing_callback_does_not_stop_the_others(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            with Transaction(self.model):
                Transaction(self.model).after_commit(self.mark('a'))
                Transaction(self.model).after_commit(self.boom())
                Transaction(self.model).after_commit(self.mark('b'))
        self.assertEqual(['a', 'b'], self.calls)
        self.assertIn('transaction callback failed', err.getvalue())
        self.assertIn('RuntimeError: callback failure', err.getvalue())

    def test_a_failing_callback_is_not_raised_to_the_caller(self):
        "The COMMIT succeeded: an exception here would deny it"
        with contextlib.redirect_stderr(io.StringIO()):
            with Transaction(self.model):
                self.pers(
                    first_name='c', last_name='cbk', birth_date='1970-01-01').ho_insert()
                Transaction(self.model).after_commit(self.boom())
        self.assertEqual(1, halftest.person_cls(last_name='cbk').ho_count())
        halftest.person_cls(last_name='cbk').ho_delete()

    def test_a_failed_commit_runs_the_rollback_callbacks(self):
        "A COMMIT that fails is a rollback, whatever the block returned"
        def deferred_violation():
            with Transaction(self.model):
                self.model.execute_query(
                    'CREATE TEMP TABLE t_cb (i int UNIQUE DEFERRABLE INITIALLY DEFERRED)'
                    ' ON COMMIT DROP')
                self.model.execute_query('INSERT INTO t_cb VALUES (1), (1)')
                Transaction(self.model).after_commit(self.mark('commit'))
                Transaction(self.model).after_rollback(self.mark('rollback'))

        self.assertRaises(psycopg.errors.UniqueViolation, deferred_violation)
        self.assertEqual(['rollback'], self.calls)

    def test_a_callback_registered_by_a_callback_runs_at_once(self):
        "The transaction is over by then"
        with Transaction(self.model):
            Transaction(self.model).after_commit(
                lambda: Transaction(self.model).after_commit(self.mark('nested')))
        self.assertEqual(['nested'], self.calls)
