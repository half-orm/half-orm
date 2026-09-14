#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Function and procedure names are interpolated into the statement, unlike
their arguments, which psycopg binds. They are therefore checked — and so are
the kwargs keys, rendered as ``key => %s``.

`f(**{'a => 1) --': v})` is legal Python, so a caller can reach the query
through a parameter name as easily as through the callable's name."""

from unittest import TestCase, IsolatedAsyncioTestCase

from half_orm.model import _check_named_params, _check_qualified_name

from ..init import halftest


INJECTION = 'public.add(1); drop table actor.person; --'


class TestCheckQualifiedName(TestCase):
    def check(self, name):
        return _check_qualified_name(name, 'function name')

    def test_accepts_plain_and_qualified_names(self):
        for name in ('add', 'public.add', 'my_schema.my_func', '_private', 'f$1'):
            self.assertEqual(self.check(name), name)

    def test_returns_the_name_unchanged(self):
        "not re-quoted: PostgreSQL must keep folding bare identifiers as before"
        self.assertEqual(self.check('MyFunc'), 'MyFunc')

    def test_accepts_quoted_segments(self):
        "a quoted segment may hold spaces, and even a dot"
        for name in ('"My Func"', '"My Schema"."My Func"', '"a.b".c'):
            self.assertEqual(self.check(name), name)

    def test_accepts_non_ascii_identifiers(self):
        "PostgreSQL allows them unquoted, and so does the grammar"
        self.assertEqual(self.check('crème'), 'crème')

    def test_rejects_injection(self):
        for name in (INJECTION, 'add; select 1', 'add() --', 'pg_sleep(10)',
                     'add, other', "add'", 'a b', 'a-b', '1f', ''):
            with self.assertRaises(ValueError, msg=f'accepted: {name!r}'):
                self.check(name)

    def test_rejects_non_string(self):
        for name in (None, 42, ['public', 'add']):
            with self.assertRaises(ValueError):
                self.check(name)

    def test_error_message_names_the_offender(self):
        with self.assertRaises(ValueError) as ctx:
            self.check(INJECTION)
        self.assertIn('drop table', str(ctx.exception))


class TestCheckNamedParams(TestCase):
    def test_accepts_identifiers(self):
        _check_named_params({'a': 1, 'my_arg': 2}, 'execute_function')

    def test_rejects_non_identifiers(self):
        for key in ('a => 1) ; drop table t; --', 'a b', '1a', 'a-b', ''):
            with self.assertRaises(ValueError, msg=f'accepted: {key!r}'):
                _check_named_params({key: 1}, 'execute_function')


class TestExecuteFunction(TestCase):
    def setUp(self):
        self.model = halftest.model

    def test_positional_call_still_works(self):
        self.assertEqual(self.model.execute_function('public.add', 3, 4)[0]['add'], 7)

    def test_named_call_still_works(self):
        rows = self.model.execute_function('public.named_add', a=10, b=5)
        self.assertEqual(rows[0]['named_add'], 15)

    def test_injected_name_rejected(self):
        with self.assertRaises(ValueError):
            self.model.execute_function(INJECTION, 1)

    def test_injected_parameter_name_rejected(self):
        with self.assertRaises(ValueError):
            self.model.execute_function('public.named_add', **{'a => 1) --': 1})

    def test_call_procedure_name_rejected(self):
        with self.assertRaises(ValueError):
            self.model.call_procedure(INJECTION)


class TestAsyncCallableNames(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.model = halftest.model
        await self.model.aconnect()

    async def test_positional_call_still_works(self):
        rows = await self.model.aexecute_function('public.add', 3, 4)
        self.assertEqual(rows[0]['add'], 7)

    async def test_injected_name_rejected(self):
        with self.assertRaises(ValueError):
            await self.model.aexecute_function(INJECTION, 1)

    async def test_injected_procedure_name_rejected(self):
        with self.assertRaises(ValueError):
            await self.model.acall_procedure(INJECTION)
