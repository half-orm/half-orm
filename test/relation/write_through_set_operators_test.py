#!/usr/bin/env python
#-*- coding:  utf-8 -*-

"""ho_update and ho_delete on a predicate built with | or - whose operands
navigate foreign keys.

Such a predicate is compiled as a UNION or EXCEPT container (see
Relation.__or__ and Relation.__sub__). ho_select and ho_count read the
container; the writes must touch exactly the same rows. A witness author's
posts must survive every write.
"""

from unittest import TestCase
from datetime import date

from ..init import halftest

WITNESS = {
    'last_name': 'Prunelle', 'first_name': 'Leon', 'birth_date': date.today()
}


class Test(TestCase):
    def setUp(self):
        self.gaston = halftest.gaston
        self.gaston.ho_insert()
        for title in ('Easy', 'Super', 'Super easy', 'Bad'):
            self.gaston.post_rfk(title=title, content='bla').ho_insert()
        self.witness = halftest.person_cls(**WITNESS)
        self.witness.ho_insert()
        for title in ('Super witness', 'Easy witness'):
            self.witness.post_rfk(title=title, content='bla').ho_insert()
        self.post_cls = halftest.post_cls

    def tearDown(self):
        self.gaston.ho_delete()
        self.witness.ho_delete()

    def titles(self, relation):
        return sorted(row['title'] for row in relation.ho_select('title'))

    def gaston_titles(self):
        return self.titles(self.gaston.post_rfk())

    def witness_titles(self):
        return self.titles(self.witness.post_rfk())

    # Union of two navigated predicates

    def union(self):
        return (self.gaston.post_rfk(title=('ilike', '%easy%')) |
                self.gaston.post_rfk(title=('ilike', '%super%')))

    def test_delete_on_union(self):
        union = self.union()
        self.assertEqual(union.ho_count(), 3)
        union.ho_delete()
        self.assertEqual(self.gaston_titles(), ['Bad'])
        self.assertEqual(self.witness_titles(), ['Easy witness', 'Super witness'])

    def test_update_on_union(self):
        self.union().ho_update(content='updated')
        updated = self.post_cls(content='updated')
        self.assertEqual(self.titles(updated), ['Easy', 'Super', 'Super easy'])

    # Difference: navigated minus plain

    def navigated_minus_plain(self):
        return self.gaston.post_rfk() - self.post_cls(title='Bad')

    def test_delete_on_navigated_minus_plain(self):
        self.navigated_minus_plain().ho_delete()
        self.assertEqual(self.gaston_titles(), ['Bad'])
        self.assertEqual(self.witness_titles(), ['Easy witness', 'Super witness'])

    def test_update_on_navigated_minus_plain(self):
        self.navigated_minus_plain().ho_update(content='updated')
        updated = self.post_cls(content='updated')
        self.assertEqual(self.titles(updated), ['Easy', 'Super', 'Super easy'])

    # Difference: plain minus navigated

    def plain_minus_navigated(self):
        return (self.post_cls(title=('ilike', '%super%')) -
                self.gaston.post_rfk(title='Super'))

    def test_delete_on_plain_minus_navigated(self):
        self.plain_minus_navigated().ho_delete()
        self.assertEqual(self.gaston_titles(), ['Bad', 'Easy', 'Super'])
        self.assertEqual(self.witness_titles(), ['Easy witness'])

    def test_update_on_plain_minus_navigated(self):
        self.plain_minus_navigated().ho_update(content='updated')
        updated = self.post_cls(content='updated')
        self.assertEqual(self.titles(updated), ['Super easy', 'Super witness'])

    # Returned rows follow the same predicate

    def test_update_returns_the_updated_rows(self):
        rows = self.union().ho_update('title', content='updated')
        self.assertEqual(sorted(row['title'] for row in rows),
                         ['Easy', 'Super', 'Super easy'])
