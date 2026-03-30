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

    # ------------------------------------------------------------------
    # Direct FK (many-to-one) — must return a dict, not a list
    # ------------------------------------------------------------------

    def test_direct_fk_returns_dict(self):
        "direct FK must return a dict (not a list)"
        with Transaction(halftest.model):
            self._insert_post('for_author', 'c')

            p = self.post(author_last_name='aa')
            p.author_fk.set(self.person())

            rows = list(p.ho_select(json_agg={'author_fk': ['last_name']}))
            self.assertEqual(len(rows), 1)
            author = rows[0]['author_fk']
            self.assertIsInstance(author, dict)
            self.assertEqual(author['last_name'], 'aa')

    def test_direct_fk_specific_fields(self):
        "direct FK with field list must include only those fields"
        with Transaction(halftest.model):
            self._insert_post('direct_fields', 'c')

            p = self.post(author_last_name='aa')
            p.author_fk.set(self.person())

            rows = list(p.ho_select(json_agg={'author_fk': ['last_name', 'first_name']}))
            author = rows[0]['author_fk']
            self.assertEqual(set(author.keys()), {'last_name', 'first_name'})

    def test_direct_fk_all_fields(self):
        "direct FK with empty field list must return all columns"
        with Transaction(halftest.model):
            self._insert_post('direct_all', 'c')

            p = self.post(author_last_name='aa')
            p.author_fk.set(self.person())

            rows = list(p.ho_select(json_agg={'author_fk': []}))
            author = rows[0]['author_fk']
            self.assertIn('last_name', author)
            self.assertIn('first_name', author)
            self.assertIn('birth_date', author)

    def test_mixed_direct_and_reverse_fk(self):
        "mixing direct FK (dict) and reverse FK (list) in one json_agg call"
        with Transaction(halftest.model):
            self._insert_post('mixed', 'content')

            p = self.post(author_last_name='aa')
            p.author_fk.set(self.person())
            p.comment_rfk.set(self.comment())

            rows = list(p.ho_select(json_agg={
                'author_fk':  ['last_name'],
                'comment_rfk': ['content'],
            }))
            self.assertEqual(len(rows), 1)
            self.assertIsInstance(rows[0]['author_fk'], dict)
            self.assertIsInstance(rows[0]['comment_rfk'], list)

    # ------------------------------------------------------------------
    # Singleton reverse FK (one-to-one via UNIQUE constraint)
    # ------------------------------------------------------------------

    def _add_unique_constraint(self):
        "Add UNIQUE(post_id) on blog.comment to simulate a one-to-one reverse FK."
        halftest.model.execute_query(
            'ALTER TABLE blog.comment ADD CONSTRAINT _test_comment_post_id_unique UNIQUE (post_id)'
        )
        halftest.model.reconnect(reload=True)

    def _drop_unique_constraint(self):
        "Remove the temporary UNIQUE constraint and reload metadata."
        halftest.model.execute_query(
            'ALTER TABLE blog.comment DROP CONSTRAINT IF EXISTS _test_comment_post_id_unique'
        )
        halftest.model.reconnect(reload=True)

    def test_singleton_reverse_fk_is_singleton_flag(self):
        "comment_rfk must report is_singleton=True after UNIQUE(post_id) is added"
        self._add_unique_constraint()
        try:
            post = self.post()
            self.assertTrue(post.comment_rfk.is_singleton)
        finally:
            self._drop_unique_constraint()

    def test_singleton_reverse_fk_returns_dict(self):
        "singleton reverse FK must return a dict (not a list)"
        self._add_unique_constraint()
        try:
            with Transaction(halftest.model):
                self._insert_post('singleton_post', 'c')
                post = self.post(author_last_name='aa')
                post.comment_rfk.set(self.comment())
                rows = list(post.ho_select(json_agg={'comment_rfk': ['content']}))
                self.assertEqual(len(rows), 1)
                self.assertIsInstance(rows[0]['comment_rfk'], (dict, type(None)))
        finally:
            self._drop_unique_constraint()

    def test_singleton_reverse_fk_with_data(self):
        "singleton reverse FK with a matching comment must return a dict with the data"
        self._add_unique_constraint()
        try:
            with Transaction(halftest.model):
                self._insert_post('singleton_with_data', 'c')
                post_row = self.post(
                    title='singleton_with_data',
                    author_last_name='aa',
                ).ho_get()
                self.comment(
                    post_id=post_row['id'],
                    content='my comment',
                ).ho_insert()

                p = self.post(title='singleton_with_data', author_last_name='aa')
                p.comment_rfk.set(self.comment())
                rows = list(p.ho_select(json_agg={'comment_rfk': ['content']}))
                self.assertEqual(len(rows), 1)
                comment = rows[0]['comment_rfk']
                self.assertIsInstance(comment, dict)
                self.assertEqual(comment['content'], 'my comment')
        finally:
            self._drop_unique_constraint()