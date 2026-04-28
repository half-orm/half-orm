#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for the crud_only connection flag."""

from unittest import TestCase
from half_orm.model import Model


class TestCrudOnly(TestCase):
    def setUp(self):
        self.model = Model('halftest_crud_only')
        self.person_cls = self.model._import_class('actor.person')

    def test_execute_query_raises(self):
        "execute_query must raise PermissionError when crud_only is set."
        with self.assertRaises(PermissionError):
            self.model.execute_query('select 1')

    def test_crud_operations_allowed(self):
        "CRUD operations via Relation methods must still work."
        count = self.person_cls().ho_count()
        self.assertGreater(count, 0)