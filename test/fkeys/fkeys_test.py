#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

import psycopg
from unittest import TestCase, skip

from ..init import halftest
from half_orm import relation_errors, model


ERR_MSG = """self.comment_rfk is not a FKey (got a Comment object instead).
- use: self.comment_rfk.set(Comment(...))
- not: self.comment_rfk = Comment(...)"""

class Test(TestCase):
    def setUp(self):
        self.pers = halftest.person_cls()
        self.post = halftest.post_cls()
        self.comment = halftest.comment_cls()
        aa = self.pers(last_name='aa')
        assert(aa.ho_count() == 1)

    def test_post_fkeys_names(self):
        self.assertEqual(
            list(self.post._ho_fkeys.keys()),
            ['_reverse_fkey_halftest_blog_comment_post_id', 'author'])

    def test_comment_fkeys_names(self):
        self.assertEqual(list(self.comment._ho_fkeys.keys()), ['post', 'author'])

    def test_post_author_fkey_type(self):
        author = self.post.author_fk()
        self.assertIsInstance(author, halftest.person_cls)

    def test_comment_author_fkey_type(self):
        author = self.comment.author_fk()
        self.assertIsInstance(author, halftest.person_cls)

    def test_comment_post_fkey_type(self):
        post = self.comment._ho_fkeys['post']()
        self.assertIsInstance(post, halftest.post_cls)

    def test_is_set(self):
        post = self.post()
        self.assertFalse(post.ho_is_set())
        pers = self.pers(last_name=('a%', 'like'))
        post.author_fk.set(pers)
        self.assertTrue(post.ho_is_set())

    def test_is_not_set(self):
        post = self.post()
        self.assertFalse(post.ho_is_set())
        pers = self.pers()
        self.assertFalse(pers.ho_is_set())
        post.author_fk.set(pers)
        self.assertFalse(post.ho_is_set())

    def test_is_set_reverse(self):
        post = self.post(title="toto")
        author = post.author_fk()
        self.assertTrue(author.ho_is_set())

    def test_is_not_set_reverse(self):
        post = self.post()
        self.assertFalse(post.author_fk.is_set())
        self.assertFalse(post.author_fk().ho_is_set())

    def test_check_FKEYS_class(self):
        pers = self.pers()
        self.assertEqual(pers.post_rfk().__class__.__name__, self.post.__class__.__name__)
        self.assertEqual(pers.comment_rfk().__class__.__name__, self.comment.__class__.__name__)
        post = self.post()
        self.assertEqual(post.author_fk().__class__.__name__, self.pers.__class__.__name__)
        self.assertEqual(post.comment_rfk().__class__.__name__, self.comment.__class__.__name__)

    def test_runtime_error(self):
        "should raise a RuntimeError exception"
        pers = self.pers()
        # A relation fkey attribute is a FKey class and the __set__ descriptor doesn't work on a class

        pers.comment_rfk = self.comment()
        err = None
        with self.assertRaises(RuntimeError) as err:
            list(pers.ho_select())
        self.assertEqual(str(err.exception), ERR_MSG)

    def test_expecting_a_relation_error(self):
        "it should raise an exception if we set with anything but a Relation object"
        with self.assertRaises(RuntimeError) as exc:
            self.pers().post_rfk.set('coucou')
        self.assertEqual(
            exc.exception.args[0],
            "Fkey.set excepts an argument of type Relation")

    def test_can_t_reference_same_relation_error(self):
        "it should raise an exception if we set with the same Relation object"
        fkey_rel = self.pers().post_rfk
        fkey_rel.set(fkey_rel())
        with self.assertRaises(RuntimeError) as exc:
            fkey_rel()
        self.assertEqual(
            exc.exception.args[0],
            "Can't set Fkey on the same object")

    def test_remote_property(self):
        self.assertEqual(self.pers().post_rfk.remote, {'fqtn': ('blog', 'post'), 'reverse': True})
        self.assertEqual(self.post().author_fk.remote, {'fqtn': ('actor', 'person'), 'reverse': False})

    def test_name_property(self):
        "it should return the name of the foreign key"
        self.assertEqual(self.pers().post_rfk.name, '_reverse_fkey_halftest_blog_post_author_first_name_author_last_name_author_birth_date')
        self.assertEqual(self.post().author_fk.name, 'author')

    def test_cast(self):
        self.assertIsInstance(halftest.comment_cls().post_fk(__cast__='blog.event'), halftest.event_cls)

    def test_cast_reverse(self):
        post = halftest.post_cls(title='coucou')
        self.pers.post_rfk(__cast__='blog.event')
        pers = halftest.person_cls(last_name='Lagaffe')
        pers.ho_mogrify()
        list(pers)
        event = pers.post_rfk(title='coucou', __cast__='blog.event')
        self.assertEqual(event.title.value, 'coucou')
        self.assertIsInstance(event, halftest.event_cls)
        event.ho_mogrify()
        list(event)
