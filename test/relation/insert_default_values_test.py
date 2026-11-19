#!/usr/bin/env python
#-*- coding:  utf-8 -*-

"""ho_insert on a relation with no field set: every column takes its
default (INSERT ... DEFAULT VALUES)."""

from unittest import TestCase

from ..init import halftest


class Test(TestCase):
    def setUp(self):
        self.post_cls = halftest.post_cls
        self.inserted = []

    def tearDown(self):
        for post_id in self.inserted:
            self.post_cls(id=post_id).ho_delete()

    def test_insert_with_no_field_set(self):
        row = self.post_cls().ho_insert()
        self.inserted.append(row['id'])
        self.assertIsNotNone(row['id'])
        self.assertIsNone(row['title'])

    def test_returning_columns(self):
        row = self.post_cls().ho_insert('id')
        self.inserted.append(row['id'])
        self.assertEqual(list(row), ['id'])
