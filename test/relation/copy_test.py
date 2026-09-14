#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for Relation.ho_copy and Relation.ho_acopy."""

import io
from datetime import date
from unittest import TestCase, IsolatedAsyncioTestCase

from half_orm import relation_errors

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


class TestHoCopyColumnNames(TestCase):
    """Column names reach COPY from outside the program.

    No parameter can stand for an identifier, so they are interpolated into
    the statement -- and they come from a CSV header or from the keys of the
    caller's dicts, both of which are routinely deserialised from a request
    body or an uploaded file.
    """

    INJECTION = 'last_name") from stdin; create table public.ho_copy_pwned(x int); --'

    def setUp(self):
        self.Person = halftest.person_cls

    def tearDown(self):
        self.Person(birth_date=TEST_DATE).ho_delete(delete_all=True)
        model.execute_query('drop table if exists public.ho_copy_pwned')

    def _pwned(self):
        try:
            model.execute_query('select 1 from public.ho_copy_pwned')
            return True
        except Exception:
            return False

    def test_csv_header_cannot_inject(self):
        with self.assertRaises(relation_errors.UnknownAttributeError):
            self.Person.ho_copy(io.StringIO(f'{self.INJECTION}\n'))
        self.assertFalse(self._pwned())

    def test_dict_key_cannot_inject(self):
        """The keys of a JSON body land here verbatim."""
        with self.assertRaises(relation_errors.UnknownAttributeError):
            self.Person.ho_copy([{self.INJECTION: 'x'}])
        self.assertFalse(self._pwned())

    def test_explicit_columns_cannot_inject(self):
        with self.assertRaises(relation_errors.UnknownAttributeError):
            self.Person.ho_copy(io.StringIO('x\n'), columns=[self.INJECTION])
        self.assertFalse(self._pwned())

    def test_a_lone_quote_is_refused(self):
        """Quoting alone would turn this into an unterminated identifier."""
        with self.assertRaises(relation_errors.UnknownAttributeError):
            self.Person.ho_copy(io.StringIO('last_name"\n'))

    def test_unknown_column_is_named_in_the_error(self):
        with self.assertRaises(relation_errors.UnknownAttributeError) as ctx:
            self.Person.ho_copy(io.StringIO('last_name,not_a_column\n'))
        self.assertIn('not_a_column', str(ctx.exception))

    def test_quoted_header_is_read_as_csv(self):
        """PostgreSQL parses the body as CSV, so the header is read the same.

        Splitting on ',' turned `"last_name"` into `""last_name""`, which
        PostgreSQL rejects as a zero-length delimited identifier -- so any
        writer that quotes every field produced an unusable file.
        """
        n = self.Person.ho_copy(io.StringIO(
            '"last_name","first_name","birth_date"\n'
            'copy_quoted,test,1800-01-01\n'))
        self.assertEqual(n, 1)
        self.assertEqual(self.Person(last_name='copy_quoted').ho_count(), 1)

    def test_empty_file_is_reported(self):
        with self.assertRaises(ValueError) as ctx:
            self.Person.ho_copy(io.StringIO(''))
        self.assertIn('header', str(ctx.exception))

    def test_header_only_whitespace_is_reported(self):
        with self.assertRaises(ValueError) as ctx:
            self.Person.ho_copy(io.StringIO('\n'))
        self.assertIn('no columns', str(ctx.exception))


class TestHoACopyColumnNames(IsolatedAsyncioTestCase):
    """The async variant shares the check; it used to share the flaw."""

    INJECTION = TestHoCopyColumnNames.INJECTION

    async def asyncSetUp(self):
        self.Person = halftest.person_cls
        await model.aconnect()

    async def asyncTearDown(self):
        self.Person(birth_date=TEST_DATE).ho_delete(delete_all=True)
        model.execute_query('drop table if exists public.ho_copy_pwned')

    async def test_csv_header_cannot_inject(self):
        with self.assertRaises(relation_errors.UnknownAttributeError):
            await self.Person.ho_acopy(io.StringIO(f'{self.INJECTION}\n'))

    async def test_dict_key_cannot_inject(self):
        with self.assertRaises(relation_errors.UnknownAttributeError):
            await self.Person.ho_acopy([{self.INJECTION: 'x'}])

    async def test_quoted_header_is_read_as_csv(self):
        n = await self.Person.ho_acopy(io.StringIO(
            '"last_name","first_name","birth_date"\n'
            'acopy_quoted,test,1800-01-01\n'))
        self.assertEqual(n, 1)


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