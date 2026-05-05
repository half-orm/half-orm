#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for ho_select(json_agg=...) — LEFT JOIN and correlated-subquery aggregation."""

from unittest import TestCase

from half_orm.transaction import Transaction

from ..init import halftest


class Test(TestCase):
    def setUp(self):
        self.person = halftest.person_cls
        self.post = halftest.post_cls
        self.comment = halftest.comment_cls
        # Use existing person 'aa' (inserted by HalfTest fixture)
        self.aa = self.person(**self.person(last_name='aa').ho_get())
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

    # ------------------------------------------------------------------
    # Chained FK (A ← B → C): person ← comment → post
    # ------------------------------------------------------------------

    def _insert_comment(self, post_id, content='comment'):
        aa = self.aa
        self.comment(
            post_id=post_id,
            content=content,
            author_id=aa['id'],
        ).ho_insert()

    def _insert_post_and_get_id(self, title, content=''):
        aa = self.aa
        row = self.post(
            title=title,
            content=content,
            author_first_name=str(aa['first_name']),
            author_last_name=str(aa['last_name']),
            author_birth_date=aa['birth_date'],
        ).ho_insert()
        return row['id']

    def test_chained_fk_returns_list_of_leaf(self):
        "post ← comment → person: must return list of person dicts per post"
        with Transaction(halftest.model):
            pid = self._insert_post_and_get_id('chained_post', 'c')
            self._insert_comment(pid, 'hello')

            p = self.post(title='chained_post')
            c = self.comment()
            c.author_fk.set(self.person())   # chain: comment → person
            p.comment_rfk.set(c)

            rows = list(p.ho_select(json_agg={'comment_rfk': ['last_name']}))
            self.assertEqual(len(rows), 1)
            persons = rows[0]['comment_rfk']
            self.assertIsInstance(persons, list)
            self.assertEqual(len(persons), 1)
            self.assertEqual(persons[0]['last_name'], 'aa')

    def test_chained_fk_empty_returns_empty_list(self):
        "post ← comment → person with no comments: must return []"
        with Transaction(halftest.model):
            self._insert_post_and_get_id('empty_chained', 'c')
            p = self.post(title='empty_chained')
            c = self.comment()
            c.author_fk.set(self.person())
            p.comment_rfk.set(c)

            rows = list(p.ho_select(json_agg={'comment_rfk': ['last_name']}))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['comment_rfk'], [])

    def test_chained_fk_branching_raises(self):
        "branching FK chain (B has two FKs set) must raise RuntimeError"
        p = self.post(title='branching')
        c = self.comment()
        c.author_fk.set(self.person())
        c.post_fk.set(self.post())       # second FK set on comment → branching
        p.comment_rfk.set(c)

        with self.assertRaises(RuntimeError) as ctx:
            list(p.ho_select(json_agg={'comment_rfk': []}))
        self.assertIn('branching', str(ctx.exception))


class TestJsonAggDistinct(TestCase):
    """Tests for ho_select(json_agg={..., 'distinct': True}).

    When 'distinct': True is set in a spec dict, the LEFT JOIN + GROUP BY
    strategy is replaced by a correlated subquery with SELECT DISTINCT,
    which deduplicates aggregated rows that would otherwise appear multiple
    times due to intermediate JOIN multiplications.
    """

    def setUp(self):
        self.person = halftest.person_cls
        self.post = halftest.post_cls
        self.comment = halftest.comment_cls
        self.aa = self.person(**self.person(last_name='aa').ho_get())
        self.ab = self.person(**self.person(last_name='ab').ho_get())
        self.post(author_last_name='aa').ho_delete(delete_all=True)

    def tearDown(self):
        self.post(author_last_name='aa').ho_delete(delete_all=True)

    def _insert_post(self, title, content=''):
        aa = self.aa
        return self.post(
            title=title,
            content=content,
            author_first_name=str(aa.first_name),
            author_last_name=str(aa.last_name),
            author_birth_date=aa.birth_date.value,
        ).ho_insert()

    def _insert_comment(self, post_id, content='comment', author_id=None):
        if author_id is None:
            author_id = self.aa['id']
        self.comment(
            post_id=post_id,
            content=content,
            author_id=author_id,
        ).ho_insert()

    # ------------------------------------------------------------------
    # Basic correctness
    # ------------------------------------------------------------------

    def test_distinct_no_related_rows_returns_empty_array(self):
        "distinct=True must return [] when the joined relation has no rows"
        p = self.person(last_name='aa')
        p.post_rfk.set(self.post())
        rows = list(p.ho_select(json_agg={
            'post_rfk': {'fields': ['title'], 'distinct': True}
        }))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['post_rfk'], [])

    def test_distinct_returns_correct_data(self):
        "distinct=True must return the same data as non-distinct when rows are unique"
        with Transaction(halftest.model):
            self._insert_post('d_unique', 'content')
            p = self.person(last_name='aa')
            p.post_rfk.set(self.post())
            rows = list(p.ho_select(json_agg={
                'post_rfk': {'fields': ['title'], 'distinct': True}
            }))
            self.assertEqual(len(rows), 1)
            posts = rows[0]['post_rfk']
            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0]['title'], 'd_unique')

    def test_distinct_all_fields(self):
        "distinct=True with empty fields list must return all columns via to_jsonb"
        with Transaction(halftest.model):
            row = self._insert_post('d_all_fields', 'c')
            self._insert_comment(row['id'], 'hello')
            p = self.post(title='d_all_fields')
            p.comment_rfk.set(self.comment())
            rows = list(p.ho_select(json_agg={
                'comment_rfk': {'fields': [], 'distinct': True}
            }))
            comments = rows[0]['comment_rfk']
            self.assertEqual(len(comments), 1)
            self.assertIn('content', comments[0])
            self.assertIn('id', comments[0])

    def test_distinct_with_alias(self):
        "distinct=True with an explicit alias must name the output column accordingly"
        with Transaction(halftest.model):
            row = self._insert_post('d_alias', 'c')
            self._insert_comment(row['id'], 'hi')
            p = self.post(title='d_alias')
            p.comment_rfk.set(self.comment())
            rows = list(p.ho_select(json_agg={
                'comment_rfk': {'fields': ['content'], 'alias': 'remarks', 'distinct': True}
            }))
            self.assertIn('remarks', rows[0])
            self.assertNotIn('comment_rfk', rows[0])

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def test_distinct_deduplicates_identical_objects(self):
        """Two comments with the same content → 1 object with distinct, 2 without.

        The DISTINCT is on the jsonb object built from the projected fields,
        so two rows that produce the same json_build_object value collapse to one.
        """
        with Transaction(halftest.model):
            row = self._insert_post('d_dup', 'c')
            pid = row['id']
            self._insert_comment(pid, content='same', author_id=self.aa['id'])
            self._insert_comment(pid, content='same', author_id=self.ab['id'])

            # without distinct: both identical objects appear
            p = self.post(title='d_dup')
            p.comment_rfk.set(self.comment())
            rows = list(p.ho_select(json_agg={'comment_rfk': ['content']}))
            self.assertEqual(len(rows[0]['comment_rfk']), 2)

            # with distinct: deduplicated to one object
            p2 = self.post(title='d_dup')
            p2.comment_rfk.set(self.comment())
            rows2 = list(p2.ho_select(json_agg={
                'comment_rfk': {'fields': ['content'], 'distinct': True}
            }))
            self.assertEqual(len(rows2[0]['comment_rfk']), 1)
            self.assertEqual(rows2[0]['comment_rfk'][0]['content'], 'same')

    def test_distinct_preserves_unique_objects(self):
        "distinct=True must keep distinct objects when their content differs"
        with Transaction(halftest.model):
            row = self._insert_post('d_uniq2', 'c')
            pid = row['id']
            self._insert_comment(pid, content='first',  author_id=self.aa['id'])
            self._insert_comment(pid, content='second', author_id=self.ab['id'])

            p = self.post(title='d_uniq2')
            p.comment_rfk.set(self.comment())
            rows = list(p.ho_select(json_agg={
                'comment_rfk': {'fields': ['content'], 'distinct': True}
            }))
            contents = {obj['content'] for obj in rows[0]['comment_rfk']}
            self.assertEqual(contents, {'first', 'second'})

    # ------------------------------------------------------------------
    # Chained FK
    # ------------------------------------------------------------------

    def test_distinct_chained_fk(self):
        "distinct=True on a chained FK (post ← comment → person) must work"
        with Transaction(halftest.model):
            row = self._insert_post('d_chained', 'c')
            self._insert_comment(row['id'], 'hello', author_id=self.aa['id'])

            p = self.post(title='d_chained')
            c = self.comment()
            c.author_fk.set(self.person())
            p.comment_rfk.set(c)
            rows = list(p.ho_select(json_agg={
                'comment_rfk': {'fields': ['last_name'], 'distinct': True}
            }))
            self.assertEqual(len(rows), 1)
            persons = rows[0]['comment_rfk']
            self.assertIsInstance(persons, list)
            self.assertEqual(persons[0]['last_name'], 'aa')

    # ------------------------------------------------------------------
    # Direct FK (scalar)
    # ------------------------------------------------------------------

    def test_distinct_direct_fk_returns_dict(self):
        "distinct=True on a direct FK must return a dict (scalar subquery)"
        with Transaction(halftest.model):
            self._insert_post('d_direct', 'c')
            p = self.post(author_last_name='aa')
            p.author_fk.set(self.person())
            rows = list(p.ho_select(json_agg={
                'author_fk': {'fields': ['last_name'], 'distinct': True}
            }))
            self.assertEqual(len(rows), 1)
            author = rows[0]['author_fk']
            self.assertIsInstance(author, dict)
            self.assertEqual(author['last_name'], 'aa')