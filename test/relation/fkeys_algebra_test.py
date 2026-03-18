#!/usr/bin/env python
#-*- coding:  utf-8 -*-

from random import randint
import psycopg
import sys
from unittest import TestCase
from datetime import date

from ..init import halftest
from half_orm import relation_errors, model

class Test(TestCase):
    def setUp(self):
        self.gaston = halftest.gaston
        self.gaston.ho_insert()
        self.gaston.post_rfk(title='Easy', content='bla').ho_insert()
        self.gaston.post_rfk(title='Super', content='bli').ho_insert()
        self.gaston.post_rfk(title='Super easy', content='blu').ho_insert()
        self.gaston.post_rfk(title='Bad', content='blo').ho_insert()

    def tearDown(self):
        self.gaston.ho_delete()

    def test_or_on_fkeys(self):
        posts = self.gaston.post_rfk(title=('ilike', '%easy%')) | self.gaston.post_rfk(title=('ilike', '%super%'))
        list(posts)
        self.assertEqual(posts.ho_count(), 3)
        posts = self.gaston.post_rfk(title=('ilike', '%easy%')) & self.gaston.post_rfk(title=('ilike', '%super%'))
        list(posts)
        self.assertEqual(posts.ho_count(), 1)
