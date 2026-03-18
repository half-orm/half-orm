#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

import psycopg
from unittest import TestCase

from ..init import halftest
from half_orm import relation_errors, model

class Test(TestCase):
    def setUp(self):
        self.post = halftest.post_cls()

    def test_jsonb(self):
        "should insert, update, delete jsonb in blog.post"
        title = 'title test_jsonb'
        self.post.title = title
        self.post.content = 'content test_jsonb'
        data = {'a': 'b'}
        self.post.data = data
        self.post.ho_insert()
        self.assertEqual(self.post.ho_count(), 1)
        self.assertEqual(next(self.post.ho_select('data'))['data'], data)
        self.post = halftest.post_cls(title=title)
        ndata = {'a': 'c'}
        self.post.ho_update(data=ndata)
        self.post = halftest.post_cls(title=title, data=ndata)
        self.assertEqual(self.post.ho_count(), 1)
        self.post.ho_delete()
        self.assertEqual(self.post.ho_count(), 0)
