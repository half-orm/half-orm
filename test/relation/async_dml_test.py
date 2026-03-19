#!/usr/bin/env python3
#-*- coding: utf-8 -*-

import asyncio
from datetime import date
from unittest import IsolatedAsyncioTestCase

import psycopg

from ..init import halftest, model

TEST_DATE = date(1900, 1, 1)


class Test(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await model.aconnect()
        self.pers = halftest.person_cls()

    async def asyncTearDown(self):
        await self.pers(birth_date=TEST_DATE).ho_adelete(delete_all=True)
        await model.adisconnect()

    # ------------------------------------------------------------------ helpers

    async def _insert(self, last_name):
        return await self.pers(
            last_name=last_name, first_name=last_name, birth_date=TEST_DATE
        ).ho_ainsert()

    # ------------------------------------------------------------------ tests

    async def test_acount(self):
        "ho_acount returns the number of matching rows."
        self.assertEqual(await self.pers().ho_acount(), 60)

    async def test_ais_empty_false(self):
        "ho_ais_empty returns False when rows exist."
        self.assertFalse(await self.pers().ho_ais_empty())

    async def test_ais_empty_true(self):
        "ho_ais_empty returns True when no row matches."
        self.assertTrue(
            await self.pers(last_name='__nonexistent__').ho_ais_empty()
        )

    async def test_ainsert(self):
        "ho_ainsert returns the inserted row as a dict."
        result = await self._insert('async_insert')
        self.assertEqual(result['last_name'], 'async_insert')
        self.assertIn('id', result)

    async def test_ainsert_duplicate_raises(self):
        "ho_ainsert raises IntegrityError on duplicate primary key."
        row = await self._insert('async_dup')
        pers = self.pers(**row)
        with self.assertRaises(psycopg.IntegrityError):
            await pers.ho_ainsert()

    async def test_aselect(self):
        "ho_aselect returns a list of dicts matching the filter."
        await self._insert('asel_one')
        await self._insert('asel_two')
        rows = await self.pers(birth_date=TEST_DATE).ho_aselect()
        self.assertEqual(len(rows), 2)
        last_names = {r['last_name'] for r in rows}
        self.assertIn('asel_one', last_names)
        self.assertIn('asel_two', last_names)

    async def test_aselect_field_filter(self):
        "ho_aselect with a field argument returns only that column."
        await self._insert('asel_field')
        rows = await self.pers(birth_date=TEST_DATE).ho_aselect('last_name')
        self.assertEqual(rows, [{'last_name': 'asel_field'}])

    async def test_aupdate(self):
        "ho_aupdate modifies matching rows."
        await self._insert('aupd_before')
        await self.pers(last_name='aupd_before').ho_aupdate(last_name='aupd_after')
        self.assertTrue(
            await self.pers(last_name='aupd_before').ho_ais_empty()
        )
        self.assertEqual(
            await self.pers(last_name='aupd_after', birth_date=TEST_DATE).ho_acount(), 1
        )

    async def test_aupdate_all_none_returns_none(self):
        "ho_aupdate with no values to set returns None without touching the DB."
        result = await self.pers(birth_date=TEST_DATE).ho_aupdate()
        self.assertIsNone(result)

    async def test_adelete(self):
        "ho_adelete removes matching rows."
        await self._insert('adel_me')
        await self.pers(last_name='adel_me').ho_adelete(delete_all=True)
        self.assertTrue(await self.pers(last_name='adel_me').ho_ais_empty())

    async def test_concurrent_aselect(self):
        "asyncio.gather runs two independent selects concurrently."
        await self._insert('conc_a')
        await self._insert('conc_b')
        a_rows, b_rows = await asyncio.gather(
            self.pers(last_name='conc_a').ho_aselect(),
            self.pers(last_name='conc_b').ho_aselect(),
        )
        self.assertEqual(len(a_rows), 1)
        self.assertEqual(len(b_rows), 1)

    async def test_acount_after_ainsert(self):
        "Count increases by 1 after an insert."
        count_before = await self.pers(birth_date=TEST_DATE).ho_acount()
        await self._insert('count_test')
        count_after = await self.pers(birth_date=TEST_DATE).ho_acount()
        self.assertEqual(count_after, count_before + 1)