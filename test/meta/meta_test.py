#!/usr/bin/env python3
# -*- coding:  utf-8 -*-

from unittest import TestCase

from ..init import halftest, model, model_with_meta, HALFTEST_STR, HALFTEST_REL_LISTS, HALFTEST_DESC


class Test(TestCase):
    def setUp(self):
        self.pg_meta = model._Model__pg_meta
        self.pg_meta_with_meta = model_with_meta._Model__pg_meta

    def test_desc(self):
        "it should return the list of relations as [(<type>, <fqrn>, [<inherits>, ...]), ...]"
        self.assertEqual(self.pg_meta.desc('halftest'), HALFTEST_DESC)

    def test_str(self):
        "it should return a well formatted string"
        self.maxDiff = None
        self.assertEqual(HALFTEST_STR, self.pg_meta.str('halftest'))

    def test_relations_list(self):
        self.maxDiff = None
        self.assertEqual(HALFTEST_REL_LISTS, self.pg_meta.relations_list('halftest'))

    def test_relations_list_with_meta(self):
        self.maxDiff = None
        print(self.pg_meta_with_meta.relations_list('halftest'))
        self.assertEqual(HALFTEST_REL_LISTS, self.pg_meta_with_meta.relations_list('halftest'))
model._Model__pg_meta