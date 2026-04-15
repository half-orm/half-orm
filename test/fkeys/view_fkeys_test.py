#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for explicit Fkeys dict support on views."""

from unittest import TestCase

from ..init import halftest, model
from half_orm.fkey import FKey


# Build an anonymous subclass of the view with explicit Fkeys so we can test
# without touching the registered PostComment class.
#
# The view "blog.view".post_comment exposes:
#   author_post_id  — actor.person.id of the post author (INNER JOIN, never NULL)
#   author_comment_id — actor.person.id of the commenter (LEFT JOIN, may be NULL)
#
# We use author_post_id → actor.person.id as a reliable direct FK for tests.

_ViewBase = model.get_relation_class('blog.view.post_comment')


class PostCommentWithFkeys(_ViewBase):
    Fkeys = {
        # direct FK: view.author_post_id → actor.person.id
        'fk_author': {
            'to': 'actor.person',
            'join': [('author_post_id',), ('id',)],
        },
        # reverse FK: view.author_comment_id ← actor.person.id
        # (semantically: find the commenter's person record)
        'rfk_commenter': {
            'to': 'actor.person',
            'join': [('author_comment_id',), ('id',)],
        },
    }


class Test(TestCase):
    def setUp(self):
        self.gaston = halftest.gaston
        self.gaston.ho_insert()
        self.gaston.post_rfk(title='Hello', content='world').ho_insert()
        self.gaston.post_rfk(title='Bye', content='world').ho_insert()
        self.view = PostCommentWithFkeys()

    def tearDown(self):
        self.gaston.ho_delete()

    def test_fk_attr_is_fkey_instance(self):
        "fk_author and rfk_commenter should be FKey instances"
        self.assertIsInstance(self.view.fk_author, FKey)
        self.assertIsInstance(self.view.rfk_commenter, FKey)

    def test_fk_is_not_reverse(self):
        "fk_ prefix should create a non-reverse FKey"
        self.assertFalse(self.view.fk_author.is_reverse)

    def test_rfk_is_reverse(self):
        "rfk_ prefix should create a reverse FKey"
        self.assertTrue(self.view.rfk_commenter.is_reverse)

    def test_fk_navigation_returns_related_relation(self):
        "fk_author() should navigate to actor.person"
        result = self.view.fk_author()
        self.assertEqual(result._qrn, '"actor"."person"')

    def test_fk_set_all_join(self):
        "fk_author.set() with no args should join all person rows"
        view = PostCommentWithFkeys()
        view.fk_author.set()
        # The joined count should equal the unjoined count (every row has an author)
        self.assertEqual(view.ho_count(), PostCommentWithFkeys().ho_count())

    def test_fk_set_filters_view(self):
        "setting fk_author to Gaston should return only Gaston's posts"
        person_cls = model.get_relation_class('actor.person')
        gaston_person = person_cls(last_name='Lagaffe')
        view = PostCommentWithFkeys()
        view.fk_author.set(gaston_person)
        self.assertEqual(view.ho_count(), 2)

    # --- validation tests ---

    def test_invalid_source_column_raises(self):
        "a dict Fkeys entry with a non-existent source column should raise ValueError"
        class BadView(_ViewBase):
            Fkeys = {
                'fk_author': {
                    'to': 'actor.person',
                    'join': [('nonexistent_col',), ('id',)],
                },
            }
        with self.assertRaises(ValueError) as ctx:
            BadView()
        self.assertIn('nonexistent_col', str(ctx.exception))

    def test_missing_prefix_raises(self):
        "a dict Fkeys entry whose key lacks rfk_/fk_ prefix should raise ValueError"
        class BadView(_ViewBase):
            Fkeys = {
                'author': {
                    'to': 'actor.person',
                    'join': [('author_post_id',), ('id',)],
                },
            }
        with self.assertRaises(ValueError) as ctx:
            BadView()
        self.assertIn("rfk_' or 'fk_'", str(ctx.exception))

    def test_malformed_join_raises(self):
        "a dict Fkeys entry with wrong join format should raise ValueError"
        class BadView(_ViewBase):
            Fkeys = {
                'fk_author': {
                    'to': 'actor.person',
                    'join': [('author_post_id', 'id')],  # one element instead of two
                },
            }
        with self.assertRaises(ValueError) as ctx:
            BadView()
        self.assertIn('join', str(ctx.exception))