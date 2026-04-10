#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for Model.aexecute_function and Model.acall_procedure."""

from unittest import IsolatedAsyncioTestCase

from ..init import model


class TestAExecuteFunction(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await model.aconnect()

    async def asyncTearDown(self):
        await model.adisconnect()

    async def test_positional_args(self):
        "aexecute_function with positional args returns the correct result."
        rows = await model.aexecute_function('public.add', 3, 4)
        self.assertEqual(rows[0]['add'], 7)

    async def test_named_args(self):
        "aexecute_function with named kwargs uses name => value syntax."
        rows = await model.aexecute_function('public.named_add', a=10, b=5)
        self.assertEqual(rows[0]['named_add'], 15)

    async def test_no_args(self):
        "aexecute_function with no args works for zero-parameter functions."
        rows = await model.aexecute_function('public.one')
        self.assertEqual(rows[0]['one'], 1)

    async def test_mixed_args_raises(self):
        "aexecute_function raises RuntimeError when both args and kwargs are given."
        with self.assertRaises(RuntimeError):
            await model.aexecute_function('public.add', 1, b=2)

    async def test_returns_list(self):
        "aexecute_function always returns a list."
        rows = await model.aexecute_function('public.one')
        self.assertIsInstance(rows, list)


class TestACallProcedure(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await model.aconnect()
        await model.aexecute_query(
            "create or replace procedure public._ho_test_noop(x integer) "
            "language sql as 'select $1'"
        )

    async def asyncTearDown(self):
        await model.aexecute_query("drop procedure if exists public._ho_test_noop(integer)")
        await model.adisconnect()

    async def test_positional_args(self):
        "acall_procedure with positional args executes without error."
        result = await model.acall_procedure('public._ho_test_noop', 42)
        self.assertIsNone(result)

    async def test_mixed_args_raises(self):
        "acall_procedure raises RuntimeError when both args and kwargs are given."
        with self.assertRaises(RuntimeError):
            await model.acall_procedure('public._ho_test_noop', 1, x=2)