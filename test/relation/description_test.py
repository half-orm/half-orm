#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

from psycopg.errors import UndefinedTable
from half_orm.hotest import HoTestCase

from ..init import halftest

class Test(HoTestCase):
    def setUp(self):
        self.pers = halftest.person_cls()
        self.post = halftest.post_cls()
        try:
            halftest.model.execute_query('drop table a_table_without_description')
        except UndefinedTable:
            pass
        halftest.model.execute_query('create table a_table_without_description (a text)')
        halftest.model._reload()
        self.no_description_table = halftest.model.get_relation_class('public.a_table_without_description')

    def tearDown(self):
        halftest.model.execute_query('drop table a_table_without_description')
        halftest.model._reload()

    def test_description(self):
        "ho_description should return description of the relation"
        self.assertEqual(
            self.post.ho_description(),
            'The table blog.post contains all the post made by a person in the blogging system.')

    def test_no_description(self):
        "ho_description should return 'No description available'"
        self.assertEqual(
            self.no_description_table.ho_description(),
            'No description available')
