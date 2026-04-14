#!/usr/bin/env python
#-*- coding:  utf-8 -*-

import contextlib
import io
import sys
import psycopg
from random import randint
from unittest import TestCase
from datetime import date

from ..init import halftest, GASTON, model
from half_orm import relation_errors
from half_orm.relation import Relation

class Test(TestCase):
    maxDiff = None
    def setUp(self):
        self.gaston = halftest.gaston
        self.gaston.ho_insert()
        self.post = halftest.post_cls()
        self.gaston.event_rfk(title='Easy', content='bla').ho_insert()
        self.gaston.post_rfk(title='Super', content='bli').ho_insert()
        self.gaston.post_rfk(title='A super easy', content='blo').ho_insert()
        self.gaston.post_rfk(title='Bad', content='blu').ho_insert()
        model.execute_query('create table column_alias_test(class int, "class + 1" int, "2 + 1" int)')
        model.reconnect(reload=True)
        self.ColumnAliasTest = model.get_relation_class(
            'public.column_alias_test',
            fields_aliases={'class': 'class_', 'class + 1': 'class_plus_one'})

    def tearDown(self):
        self.gaston.ho_delete()
        model.execute_query('drop table column_alias_test')
        model.reconnect(reload=True)

    def test_ho_only(self):
        "it should set ONLY to select SQL request"
        posts1 = self.gaston.post_rfk(title=('ilike', '%easy%'))
        posts1.ho_only = False
        self.assertEqual(posts1.ho_count(), 2)
        posts2 = self.gaston.post_rfk(title=('ilike', '%super%'))
        posts = posts1 | posts2
        list(posts)
        self.assertEqual(posts.ho_count(), 3)
        posts1.ho_only = True
        self.assertEqual(posts1.ho_count(), 1)
        posts = self.gaston.post_rfk(title=('ilike', '%easy%')) & self.gaston.post_rfk(title=('ilike', '%super%'))
        list(posts)
        self.assertEqual(posts.ho_count(), 1)

    def test_ho_only_accepts_only_bool_values(self):
        "ho_only should only accept boolean values"
        with self.assertRaises(ValueError) as err:
            self.post.ho_only = 'coucou'
        self.assertEqual(str(err.exception), 'coucou is not a bool!')

    def test_ho_dict(self):
        "it should return the dict with the set values"
        self.assertEqual(self.gaston.ho_dict(), GASTON)

    def test_ho_dict_empty(self):
        "it should return an empty dict if the relation is not constrain"
        self.assertEqual(halftest.person_cls().ho_dict(), {})

    def test_ho_order_by(self):
        "it should return the set ordered by..."
        list_ = ['Easy', 'Super', 'A super easy', 'Bad']
        posts = halftest.post_cls()
        self.assertEqual([elt['title'] for elt in posts.ho_select(order_by='content, title')], list_)
        ordered_list_on_title = sorted(list_)
        self.assertEqual([elt['title'] for elt in posts.ho_select(order_by='title')], ordered_list_on_title)
        self.assertEqual([elt['title'] for elt in posts.ho_select(order_by='title desc')], list(reversed(ordered_list_on_title)))

    def test_ho_limit(self):
        "it should return the set limited to limit"
        posts = halftest.post_cls()
        limit = randint(1, posts.ho_count())
        self.assertEqual(len(list(posts.ho_select(order_by='content, title', limit=limit))), limit)

    def test_ho_limit_with_no_limit(self):
        "it should return the full set when no limit is given"
        posts = halftest.post_cls()
        self.assertEqual(len(list(posts.ho_select(limit=1))), 1)
        self.assertEqual(len(list(posts.ho_select())), posts.ho_count())

    def test_ho_limit_error(self):
        "it should raise a ValueError for non-integer limit"
        with self.assertRaises(ValueError):
            list(halftest.post_cls().ho_select(limit="a"))

    def test_ho_offset(self):
        "it should skip the given number of rows"
        posts = halftest.post_cls()
        total = posts.ho_count()
        offset = randint(0, total)
        self.assertEqual(len(list(posts.ho_select(offset=offset))), total - offset)

    def test_ho_offset_error(self):
        "it should raise a ValueError for non-integer offset"
        with self.assertRaises(ValueError):
            list(halftest.post_cls().ho_select(offset="a"))

    def test_cast(self):
        "it should cast to the new relation"
        events = halftest.post_cls().ho_cast('blog.event')
        self.assertEqual(events.ho_count(), 1)

    def test_cast_error(self):
        "it should raise CastError when the target is not in the inheritance hierarchy"
        with self.assertRaises(relation_errors.CastError):
            halftest.post_cls(title='coucou').ho_cast('actor.person')

    def test_field_aliases(self):
        "it should alias weird field names"
        self.assertEqual('class_', self.ColumnAliasTest()._Relation__py_field_name('class', 1))
        self.assertEqual('class_plus_one', self.ColumnAliasTest()._Relation__py_field_name('class + 1', 2))
        self.assertEqual('column3', self.ColumnAliasTest()._Relation__py_field_name('1 + 1', 3))
        self.ColumnAliasTest().class_.set(3)
        self.ColumnAliasTest(class_plus_one=4, column3=12)
        self.assertEqual(self.ColumnAliasTest().column3.name, '2 + 1')
        
    def test_wrong_field_name_err_msg(self):
        "it should write a warning message on stderr"
        out = io.StringIO()
        value1 = ''
        with contextlib.redirect_stderr(out):
            self.ColumnAliasTest()
            value1 = out.getvalue()
        self.assertEqual(value1, '\x1b[1mHALFORM WARNING\x1b[0m: "2 + 1" is not a valid identifier in Python.\n')

    def test_ho_dataclass_name(self):
        self.assertEqual(halftest.comment_cls._ho_dataclass_name(), 'DC_BlogComment')

    def test_field_set_and_kwargs(self):
        "it should be able to set fields with kwargs and Field.set"
        event = halftest.event_cls(id=1, title='coucou', end='2024-01-01')
        event.content.set('re coucou')
        event.begin.set('2024-01-01')
        self.assertTrue(event.id.is_set())
        self.assertTrue(event.title.is_set())
        self.assertTrue(event.content.is_set())
        self.assertTrue(event.end.is_set())
        self.assertTrue(event.begin.is_set())
