#!/usr/bin/env python
# -*- coding:  utf-8 -*-

from unittest import IsolatedAsyncioTestCase
from psycopg.errors import UniqueViolation
from half_orm.transaction import AsyncTransaction
from half_orm.relation import atransaction

from ..init import halftest


class APers(halftest.person_cls):
    @atransaction
    async def unique_violation(self):
        for name in ['zbc', 'zbd', 'aa']:
            await self(
                first_name=name[0], last_name=name, birth_date='1970-01-01'
            ).ho_ainsert()


class Test(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await halftest.model.aconnect()
        self.pers = halftest.person_cls()
        self.post = halftest.post_cls()
        self.today = halftest.today

    async def test_atransaction_rollback(self):
        "Should rollback with correct error"
        with self.assertRaises(UniqueViolation):
            await APers().unique_violation()
        self.assertEqual(60, await self.pers.ho_acount())

    async def test_atransaction_rollback_to_level_0(self):
        "Should rollback to level 0 if nested transaction"
        async def uniq_violation2(pers):
            self.assertEqual(AsyncTransaction(halftest.model).level, 2)
            for name in ['zxc', 'zxd']:
                await pers.__class__(
                    first_name=name, last_name=name, birth_date='1970-01-01'
                ).ho_ainsert()

        async def uniq_violation1(pers):
            self.assertEqual(AsyncTransaction(halftest.model).level, 1)
            async with AsyncTransaction(halftest.model):
                await uniq_violation2(pers)
            for name in ['zbc', 'zbd', 'aa']:
                await pers.__class__(
                    first_name=name, last_name=name, birth_date='1970-01-01'
                ).ho_ainsert()

        async def error():
            async with AsyncTransaction(halftest.model):
                await uniq_violation1(self.pers)

        with self.assertRaises(UniqueViolation):
            await error()
        self.assertEqual(AsyncTransaction(halftest.model).level, 0)

    async def test_savepoint_isolation(self):
        "Inner @atransaction failure must not abort the outer transaction"
        class APers2(halftest.person_cls):
            @atransaction
            async def ainsert_one(self, **kwargs):
                await self(**kwargs).ho_ainsert()

        initial_count = await self.pers.ho_acount()
        try:
            async with AsyncTransaction(halftest.model):
                await APers2().ainsert_one(
                    first_name='zx', last_name='zx', birth_date='2000-01-01')
                try:
                    # duplicate → UniqueViolation, rolled back via savepoint
                    await APers2().ainsert_one(
                        first_name='aa', last_name='aa', birth_date='1970-01-01')
                except UniqueViolation:
                    pass
                # outer transaction is still valid: zx/zx is committed, aa/aa was rolled back
            self.assertEqual(initial_count + 1, await self.pers.ho_acount())
        finally:
            await halftest.person_cls(first_name='zx', last_name='zx').ho_adelete()

    async def test_nested_with_savepoint_isolation(self):
        "Nested 'async with AsyncTransaction' failure must not abort the outer transaction"
        initial_count = await self.pers.ho_acount()
        try:
            async with AsyncTransaction(halftest.model):
                await self.pers(
                    first_name='zy', last_name='zy', birth_date='2000-01-01'
                ).ho_ainsert()
                try:
                    async with AsyncTransaction(halftest.model):   # savepoint
                        # duplicate → UniqueViolation, rolled back to savepoint
                        await self.pers(
                            first_name='aa', last_name='aa', birth_date='1970-01-01'
                        ).ho_ainsert()
                except UniqueViolation:
                    pass
                # outer transaction still valid: zy/zy committed, aa/aa rolled back
            self.assertEqual(initial_count + 1, await self.pers.ho_acount())
        finally:
            await halftest.person_cls(first_name='zy', last_name='zy').ho_adelete()
