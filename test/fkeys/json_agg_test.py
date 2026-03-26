#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for ho_select(json_agg=...) — LEFT JOIN + json_agg aggregation."""

from unittest import TestCase

from half_orm.transaction import Transaction

from ..init import halftest


class Test(TestCase):
    def setUp(self):
        self.person = halftest.person_cls
        self.post = halftest.post_cls
        self.comment = halftest.comment_cls
        # Use existing person 'aa' (inserted by HalfTest fixture)
        self.aa = self.person(last_name='aa').ho_get()
        # Clean any leftover posts
        self.post(author_last_name='aa').ho_delete(delete_all=True)

    def tearDown(self):
        self.post(author_last_name='aa').ho_delete(delete_all=True)

    def _insert_post(self, title, content=''):
        aa = self.aa
        self.post(
            title=title,
            content=content,
            author_first_name=str(aa.first_name),
            author_last_name=str(aa.last_name),
            author_birth_date=aa.birth_date.value,
        ).ho_insert()

    # ------------------------------------------------------------------
    # Basic behaviour
    # ------------------------------------------------------------------

    def test_no_related_rows_returns_empty_array(self):
        "json_agg must return [] when the joined relation is empty"
        p = self.person(last_name='aa')
        p.post_rfk.set(self.post())
        rows = list(p.ho_select(json_agg={'post_rfk': ['id', 'title']}))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['post_rfk'], [])

    def test_specific_fields(self):
        "json_agg must include only the requested fields in each JSON object"
        with Transaction(halftest.model):
            self._insert_post('first', 'c1')
            self._insert_post('second', 'c2')

            p = self.person(last_name='aa')
            p.post_rfk.set(self.post())

            rows = list(p.ho_select(json_agg={'post_rfk': ['id', 'title']}))
            self.assertEqual(len(rows), 1)
            posts = rows[0]['post_rfk']
            self.assertEqual(len(posts), 2)
            titles = {obj['title'] for obj in posts}
            self.assertEqual(titles, {'first', 'second'})
            for obj in posts:
                self.assertEqual(set(obj.keys()), {'id', 'title'})

    def test_all_fields(self):
        "json_agg with no field list must return all columns"
        with Transaction(halftest.model):
            self._insert_post('all_fields', 'content')

            p = self.person(last_name='aa')
            p.post_rfk.set(self.post())

            rows = list(p.ho_select(json_agg={'post_rfk': []}))
            posts = rows[0]['post_rfk']
            self.assertEqual(len(posts), 1)
            # row_to_json includes all columns
            self.assertIn('title', posts[0])
            self.assertIn('content', posts[0])
            self.assertIn('id', posts[0])

    def test_filtered_join(self):
        "json_agg must respect filters set on the joined relation"
        with Transaction(halftest.model):
            self._insert_post('alpha', 'ca')
            self._insert_post('beta', 'cb')

            p = self.person(last_name='aa')
            p.post_rfk.set(self.post(title='alpha'))  # only the 'alpha' post

            rows = list(p.ho_select(json_agg={'post_rfk': ['title']}))
            self.assertEqual(len(rows), 1)
            posts = rows[0]['post_rfk']
            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0]['title'], 'alpha')

    def test_dict_spec_with_alias(self):
        "dict spec with explicit alias must name the output column accordingly"
        with Transaction(halftest.model):
            self._insert_post('titled', 'c')

            p = self.person(last_name='aa')
            p.post_rfk.set(self.post())

            rows = list(p.ho_select(
                json_agg={'post_rfk': {'alias': 'posts', 'fields': ['title']}}))
            self.assertIn('posts', rows[0])
            self.assertNotIn('post_rfk', rows[0])
            self.assertEqual(rows[0]['posts'][0]['title'], 'titled')

    def test_dict_spec_without_alias_uses_fkey_attr(self):
        "dict spec without alias defaults to the fkey attribute name"
        with Transaction(halftest.model):
            self._insert_post('check', 'c')

            p = self.person(last_name='aa')
            p.post_rfk.set(self.post())

            rows = list(p.ho_select(
                json_agg={'post_rfk': {'fields': ['title']}}))
            self.assertIn('post_rfk', rows[0])

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_fkey_not_set_raises(self):
        "ho_select(json_agg=...) must raise when the fkey was not set via .set()"
        p = self.person(last_name='aa')
        # post_rfk has NOT been set
        with self.assertRaises(RuntimeError) as ctx:
            list(p.ho_select(json_agg={'post_rfk': []}))
        self.assertIn('post_rfk', str(ctx.exception))

    def test_unknown_attr_raises(self):
        "ho_select(json_agg=...) must raise for unknown attribute names"
        p = self.person(last_name='aa')
        with self.assertRaises(RuntimeError):
            list(p.ho_select(json_agg={'no_such_fkey': []}))