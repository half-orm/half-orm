#!/usr/bin/env python
# -*- coding:  utf-8 -*-

"""@transaction and @atransaction on something that is not a Relation method
raise a TypeError that says so."""

from unittest import IsolatedAsyncioTestCase, TestCase

from half_orm.relation import atransaction, transaction

from ..init import halftest


class Pers(halftest.person_cls):
    @staticmethod
    @transaction
    def static_write(values):
        return values

    @staticmethod
    @atransaction
    async def astatic_write(values):
        return values


class Test(TestCase):
    def test_staticmethod_is_refused(self):
        with self.assertRaisesRegex(TypeError, r"@transaction decorates a method of a Relation subclass: "
                                               r"Pers\.static_write\(\) got 'list'"):
            Pers.static_write([1, 2])

    def test_relation_method_still_works(self):
        @transaction
        def count(relation):
            return relation.ho_count()

        self.assertEqual(count(halftest.person_cls(last_name='no such name')), 0)


class ATest(IsolatedAsyncioTestCase):
    async def test_async_staticmethod_is_refused(self):
        with self.assertRaisesRegex(TypeError, r"@atransaction decorates a method of a Relation subclass"):
            await Pers.astatic_write([1, 2])
