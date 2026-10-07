#!/usr/bin/env python
# -*- coding:  utf-8 -*-

import contextlib
import io

from unittest import IsolatedAsyncioTestCase

from half_orm.transaction import AsyncTransaction

from ..init import halftest


class Test(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await halftest.model.aconnect()
        self.model = halftest.model
        self.pers = halftest.person_cls()
        self.calls = []

    async def asyncTearDown(self):
        "No test may leave a frame of callbacks behind."
        self.assertEqual(0, AsyncTransaction(self.model).level)
        self.calls.clear()
        await AsyncTransaction(self.model).after_commit(self.mark('left over'))
        self.assertEqual(['left over'], self.calls)

    def mark(self, tag):
        "A plain callback recording that it ran."
        return lambda: self.calls.append(tag)

    def amark(self, tag):
        "A coroutine callback recording that it ran."
        async def callback():
            self.calls.append(tag)
        return callback

    async def test_outside_a_transaction_the_callback_is_awaited_at_once(self):
        await AsyncTransaction(self.model).after_commit(self.amark('a'))
        self.assertEqual(['a'], self.calls)

    async def test_outside_a_transaction_after_rollback_is_dropped(self):
        await AsyncTransaction(self.model).after_rollback(self.amark('a'))
        self.assertEqual([], self.calls)

    async def test_callback_runs_after_the_commit(self):
        async with AsyncTransaction(self.model):
            await AsyncTransaction(self.model).after_commit(self.amark('a'))
            self.assertEqual([], self.calls)
        self.assertEqual(['a'], self.calls)

    async def test_coroutine_and_plain_callbacks_run_in_registration_order(self):
        async with AsyncTransaction(self.model):
            await AsyncTransaction(self.model).after_commit(self.amark('a'))
            await AsyncTransaction(self.model).after_commit(self.mark('b'))
            await AsyncTransaction(self.model).after_commit(self.amark('c'))
        self.assertEqual(['a', 'b', 'c'], self.calls)

    async def test_callback_sees_the_committed_rows(self):
        async def count():
            self.calls.append(await halftest.person_cls(last_name='acbk').ho_acount())

        try:
            async with AsyncTransaction(self.model):
                await self.pers(
                    first_name='c', last_name='acbk', birth_date='1970-01-01'
                ).ho_ainsert()
                await AsyncTransaction(self.model).after_commit(count)
            self.assertEqual([1], self.calls)
        finally:
            await halftest.person_cls(last_name='acbk').ho_adelete()

    async def test_rollback_drops_the_commit_callbacks(self):
        with self.assertRaises(RuntimeError):
            async with AsyncTransaction(self.model):
                await self.pers(
                    first_name='c', last_name='acbk', birth_date='1970-01-01'
                ).ho_ainsert()
                await AsyncTransaction(self.model).after_commit(self.amark('commit'))
                await AsyncTransaction(self.model).after_rollback(self.amark('rollback'))
                raise RuntimeError
        self.assertEqual(['rollback'], self.calls)
        self.assertTrue(await halftest.person_cls(last_name='acbk').ho_ais_empty())

    async def test_savepoint_rollback_drops_only_its_own_callbacks(self):
        async with AsyncTransaction(self.model):
            await AsyncTransaction(self.model).after_commit(self.amark('outer'))
            with self.assertRaises(RuntimeError):
                async with AsyncTransaction(self.model):
                    await AsyncTransaction(self.model).after_commit(self.amark('inner'))
                    await AsyncTransaction(self.model).after_rollback(
                        self.amark('inner undone'))
                    raise RuntimeError
            self.assertEqual(['inner undone'], self.calls)
        self.assertEqual(['inner undone', 'outer'], self.calls)

    async def test_released_savepoint_hands_its_callbacks_to_the_enclosing_scope(self):
        async with AsyncTransaction(self.model):
            async with AsyncTransaction(self.model):
                await AsyncTransaction(self.model).after_commit(self.amark('inner'))
            await AsyncTransaction(self.model).after_commit(self.amark('outer'))
            self.assertEqual([], self.calls)
        self.assertEqual(['inner', 'outer'], self.calls)

    async def test_released_savepoint_follows_the_enclosing_rollback(self):
        with self.assertRaises(RuntimeError):
            async with AsyncTransaction(self.model):
                async with AsyncTransaction(self.model):
                    await AsyncTransaction(self.model).after_commit(self.amark('inner'))
                    await AsyncTransaction(self.model).after_rollback(
                        self.amark('inner undone'))
                raise RuntimeError
        self.assertEqual(['inner undone'], self.calls)

    async def test_a_failing_callback_does_not_stop_the_others(self):
        async def boom():
            raise RuntimeError('callback failure')

        with contextlib.redirect_stderr(io.StringIO()) as err:
            async with AsyncTransaction(self.model):
                await AsyncTransaction(self.model).after_commit(self.amark('a'))
                await AsyncTransaction(self.model).after_commit(boom)
                await AsyncTransaction(self.model).after_commit(self.amark('b'))
        self.assertEqual(['a', 'b'], self.calls)
        self.assertIn('transaction callback failed', err.getvalue())
        self.assertIn('RuntimeError: callback failure', err.getvalue())
