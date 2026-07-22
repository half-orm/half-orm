#!/usr/bin/env python3
#-*- coding: utf-8 -*-

"""Async parity tests for ho_aselect(json_agg=...) — mirrors
test/fkeys/json_agg_test.py's sync coverage of ho_select(json_agg=...),
using the same halftest fixtures (person/post/comment).

All setup uses ho_ainsert (async connection, autocommit) rather than the
sync ho_insert/Transaction() combo the sync test file uses — mixing a
sync, explicitly-transactional insert with an async read across two
separate physical connections leaves the async side unable to see the
sync side's not-yet-committed rows.
"""

from unittest import IsolatedAsyncioTestCase

from ..init import halftest, model


class Test(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await model.aconnect()
        self.person = halftest.person_cls
        self.post = halftest.post_cls
        self.comment = halftest.comment_cls
        self.aa = self.person(**self.person(last_name='aa').ho_get())
        await self.post(author_last_name='aa').ho_adelete(delete_all=True)

    async def asyncTearDown(self):
        await self.post(author_last_name='aa').ho_adelete(delete_all=True)
        await model.adisconnect()

    async def _insert_post(self, title, content=''):
        aa = self.aa
        return await self.post(
            title=title,
            content=content,
            author_first_name=str(aa.first_name),
            author_last_name=str(aa.last_name),
            author_birth_date=aa.birth_date.value,
        ).ho_ainsert()

    async def test_no_related_rows_returns_empty_array(self):
        "ho_aselect(json_agg=...) must return [] when the joined relation is empty"
        p = self.person(last_name='aa')
        p.post_rfk.set(self.post())
        rows = await p.ho_aselect(json_agg={'post_rfk': ['id', 'title']})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['post_rfk'], [])

    async def test_specific_fields(self):
        "ho_aselect(json_agg=...) must include only the requested fields"
        await self._insert_post('a_first', 'c1')
        await self._insert_post('a_second', 'c2')

        p = self.person(last_name='aa')
        p.post_rfk.set(self.post())

        rows = await p.ho_aselect(json_agg={'post_rfk': ['id', 'title']})
        self.assertEqual(len(rows), 1)
        posts = rows[0]['post_rfk']
        self.assertEqual(len(posts), 2)
        titles = {obj['title'] for obj in posts}
        self.assertEqual(titles, {'a_first', 'a_second'})
        for obj in posts:
            self.assertEqual(set(obj.keys()), {'id', 'title'})

    async def test_direct_fk_returns_dict(self):
        "direct FK must return a dict (not a list), async parity"
        await self._insert_post('a_for_author', 'c')

        p = self.post(author_last_name='aa')
        p.author_fk.set(self.person())

        rows = await p.ho_aselect(json_agg={'author_fk': ['last_name']})
        self.assertEqual(len(rows), 1)
        author = rows[0]['author_fk']
        self.assertIsInstance(author, dict)
        self.assertEqual(author['last_name'], 'aa')

    async def test_chained_fk_returns_list_of_leaf(self):
        "post <- comment -> person: must return list of person dicts per post"
        row = await self._insert_post('a_chained_post', 'c')
        await self.comment(
            post_id=row['id'], content='hello', author_id=self.aa['id'],
        ).ho_ainsert()

        p = self.post(title='a_chained_post')
        c = self.comment()
        c.author_fk.set(self.person())   # chain: comment -> person
        p.comment_rfk.set(c)

        rows = await p.ho_aselect(json_agg={'comment_rfk': ['last_name']})
        self.assertEqual(len(rows), 1)
        persons = rows[0]['comment_rfk']
        self.assertIsInstance(persons, list)
        self.assertEqual(len(persons), 1)
        self.assertEqual(persons[0]['last_name'], 'aa')

    async def test_fkey_not_set_raises(self):
        "ho_aselect(json_agg=...) must raise when the fkey was not set via .set()"
        p = self.person(last_name='aa')
        with self.assertRaises(RuntimeError) as ctx:
            await p.ho_aselect(json_agg={'post_rfk': []})
        self.assertIn('post_rfk', str(ctx.exception))

    async def test_distinct_string_field_returns_scalar_list(self):
        "distinct=True with a string field returns a flat deduplicated list, async parity"
        row = await self._insert_post('a_d_scalar1', 'c')
        await self.comment(post_id=row['id'], content='hello', author_id=self.aa['id']).ho_ainsert()
        await self.comment(post_id=row['id'], content='hello', author_id=self.aa['id']).ho_ainsert()

        p = self.post(title='a_d_scalar1')
        p.comment_rfk.set(self.comment())
        rows = await p.ho_aselect(json_agg={
            'comment_rfk': {'fields': 'content', 'distinct': True}
        })
        self.assertEqual(len(rows), 1)
        contents = rows[0]['comment_rfk']
        self.assertEqual(contents, ['hello'])
