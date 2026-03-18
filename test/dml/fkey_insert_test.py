#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

import psycopg
from unittest import TestCase

from ..init import halftest
from half_orm import relation_errors, model

class Test(TestCase):
    def setUp(self):
        self.pers = halftest.person_cls()
        self.post = halftest.post_cls()
        self.comment = halftest.comment_cls()
        self.aa = self.pers(last_name='aa')
        self.ab = self.pers(last_name='ab')
        assert(self.aa.ho_count() == 1)

    def tearDown(self):
        self.pers.post_rfk().ho_delete(delete_all=True)

    def test_fkey_insert(self):
        "should insert blog.post with fkey reference on author"
        self.post.author_fk.set(self.aa)
        self.post.title.set('title test_direct_fkey_insert')
        self.post.content.set('content test_direct_fkey_insert')
        self.post.ho_insert()
        post = halftest.post_cls(title='title test_direct_fkey_insert')
        self.assertEqual(post.ho_count(), 1)
        self.assertEqual(self.aa.post_rfk().ho_count(), 1)
        self.assertEqual(post.author_fk(last_name='aa').ho_count(), 1)
        self.post.ho_delete()
        self.assertEqual(post.ho_count(), 0)
        self.assertEqual(self.aa.post_rfk().ho_count(), 0)

    def test_fkey_insert_2(self):
        self.assertEqual(self.pers.post_rfk().ho_count(), 0)
        self.aa.post_rfk(title='a post', content='test').ho_insert()
        self.assertEqual(self.aa.post_rfk().ho_count(), 1)
        self.ab.post_rfk(title='a second post', content='test').ho_insert()
        self.assertEqual(self.ab.post_rfk().ho_count(), 1)
        self.assertEqual(self.pers.post_rfk().ho_count(), 2)
