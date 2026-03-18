#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

import subprocess
from unittest import TestCase

import psycopg
from psycopg.errors import UndefinedTable

from ..init import halftest, model

TEST = 'public.test'

class Test(TestCase):
    def setUp(self):
        self.pers = halftest.person_cls()

    def tearDown(self):
        try:
            model.ping()
            model.execute_query('drop table test')
            model.disconnect()
        except UndefinedTable:
            pass

    def test_connection(self):
        self.assertEqual(halftest.dbname, 'halftest')

    def test_relation_instanciation(self):
        person = halftest.relation("actor.person")
        self.assertEqual(person._fqrn, '"halftest":"actor"."person"')
        post = halftest.relation("blog.post")
        self.assertEqual(post._fqrn, '"halftest":"blog"."post"')
        person = halftest.relation("blog.comment")
        self.assertEqual(person._fqrn, '"halftest":"blog"."comment"')
        person = halftest.relation("blog.view.post_comment")
        self.assertEqual(person._fqrn, '"halftest":"blog.view"."post_comment"')

    def test_disconnect(self):
        "it should disconnect"
        model.disconnect()
        with self.assertRaises((psycopg.InterfaceError, psycopg.OperationalError)):
            model.execute_query("select 1")

    def test_ping(self):
        "it shoud reconnect"
        model.disconnect()
        model.ping()
        self.assertEqual(1, model.execute_query("select 1").fetchone()['?column?'])

    def test_reload_and_has_relation(self):
        "it should _reload the model"
        self.assertFalse(model.has_relation(TEST))
        model.execute_query('create table test (class_ text)')
        model.execute_query('select * from test')
        model._reload()
        Test = model.get_relation_class(TEST)
        coucou = Test(class_='coucou')
        coucou.ho_insert()
        self.assertEqual(coucou.ho_count(), 1)
        print('XXX', list(coucou))
        coucou.ho_update(class_='truc')
        self.assertEqual(coucou.class_.value, 'truc')
        coucou.ho_delete()
        self.assertEqual(Test().ho_count(), 0)
        self.assertTrue(model.has_relation(TEST))
        model.execute_query('drop table test')
        model.reconnect(reload=True)
        self.assertFalse(model.has_relation(TEST))

    def test_model(self):
        "it should have load model"
        self.assertEqual(model.desc(), [('r', ('halftest', 'actor', 'person'), []), ('r', ('halftest', 'blog', 'comment'), []), ('r', ('halftest', 'blog', 'event'), [('halftest', 'blog', 'post')]), ('r', ('halftest', 'blog', 'post'), []), ('v', ('halftest', 'blog.view', 'post_comment'), [])])
