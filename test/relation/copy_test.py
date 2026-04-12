#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for Relation.ho_copy and Relation.ho_acopy."""

import io
from datetime import date
from unittest import TestCase, IsolatedAsyncioTestCase

from ..init import halftest, model

TEST_DATE = date(1800, 1, 1)
ROWS = [
    {'last_name': 'copy_A', 'first_name': 'test', 'birth_date': TEST_DATE},
    {'last_name': 'copy_B', 'first_name': 'test', 'birth_date': TEST_DATE},
    {'last_name': 'copy_C', 'first_name': 'test', 'birth_date': TEST_DATE},
]


class TestHoCopy(TestCase):
    def setUp(self):
        self.Person = halftest.person_cls

    def tearDown(self):
        self.Person(birth_date=TEST_DATE).ho_delete(delete_all=True)

    def test_copy_from_dicts_rowcount(self):
        "ho_copy returns the number of inserted rows."
        n = self.Person.ho_copy(ROWS)
        self.assertEqual(n, 3)

    def test_copy_from_dicts_data_present(self):
        "rows inserted by ho_copy are actually in the table."
        self.Person.ho_copy(ROWS)
        self.assertEqual(self.Person(birth_date=TEST_DATE).ho_count(), 3)

    def test_copy_from_dicts_values_correct(self):
        "ho_copy inserts the correct field values."
        self.Person.ho_copy(ROWS)
        names = {r['last_name'] for r in self.Person(birth_date=TEST_DATE).ho_select('last_name')}
        self.assertEqual(names, {'copy_A', 'copy_B', 'copy_C'})

    def test_copy_empty_raises(self):
        "ho_copy raises ValueError on an empty list."
        with self.assertRaises(ValueError):
            self.Person.ho_copy([])

    def test_copy_from_csv_with_header(self):
        "ho_copy accepts a file-like CSV with a header row."
        csv = io.StringIO(
            "last_name,first_name,birth_date\n"
            "copy_csv_A,test,1800-01-01\n"
            "copy_csv_B,test,1800-01-01\n"
        )
        n = self.Person.ho_copy(csv)
        self.assertEqual(n, 2)
        self.assertEqual(self.Person(birth_date=TEST_DATE).ho_count(), 2)

    def test_copy_from_csv_no_header_with_columns(self):
        "ho_copy accepts a headerless CSV when columns are given explicitly."
        csv = io.StringIO(
            "copy_nh_A,test,1800-01-01\n"
            "copy_nh_B,test,1800-01-01\n"
        )
        n = self.Person.ho_copy(csv, columns=['last_name', 'first_name', 'birth_date'])
        self.assertEqual(n, 2)
        self.assertEqual(self.Person(birth_date=TEST_DATE).ho_count(), 2)


class TestHoACopy(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await model.aconnect()
        self.Person = halftest.person_cls

    async def asyncTearDown(self):
        self.Person(birth_date=TEST_DATE).ho_delete(delete_all=True)
        await model.adisconnect()

    async def test_acopy_from_dicts_rowcount(self):
        "ho_acopy returns the number of inserted rows."
        n = await self.Person.ho_acopy(ROWS)
        self.assertEqual(n, 3)

    async def test_acopy_from_dicts_data_present(self):
        "rows inserted by ho_acopy are actually in the table."
        await self.Person.ho_acopy(ROWS)
        self.assertEqual(self.Person(birth_date=TEST_DATE).ho_count(), 3)

    async def test_acopy_empty_raises(self):
        "ho_acopy raises ValueError on an empty list."
        with self.assertRaises(ValueError):
            await self.Person.ho_acopy([])

    async def test_acopy_from_csv_with_header(self):
        "ho_acopy accepts a file-like CSV with a header row."
        csv = io.StringIO(
            "last_name,first_name,birth_date\n"
            "acopy_csv_A,test,1800-01-01\n"
        )
        n = await self.Person.ho_acopy(csv)
        self.assertEqual(n, 1)
        self.assertEqual(self.Person(birth_date=TEST_DATE).ho_count(), 1)