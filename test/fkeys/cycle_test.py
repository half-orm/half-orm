#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

from unittest import TestCase

from ..init import halftest


class Test(TestCase):
    "FKey cycle detection tests"

    def setUp(self):
        self.person = halftest.person_cls
        self.post = halftest.post_cls
        self.comment = halftest.comment_cls

    def test_direct_cycle_raises(self):
        "A → B → A via set() must raise RuntimeError"
        post = self.post()
        person = self.person()
        post.author_fk.set(person)        # post → person (OK)
        with self.assertRaises(RuntimeError):
            person.post_rfk.set(post)     # person → post would close the loop

    def test_long_cycle_raises(self):
        "A → B → C → A via set() must raise RuntimeError"
        comment = self.comment()
        post = self.post()
        person = self.person()
        comment.post_fk.set(post)         # comment → post (OK)
        post.author_fk.set(person)        # post → person (OK)
        with self.assertRaises(RuntimeError):
            person.comment_rfk.set(comment)  # person → comment would close the loop

    def test_valid_chain_does_not_raise(self):
        "A → B → C without cycle must not raise"
        comment = self.comment()
        post = self.post()
        person = self.person()
        comment.post_fk.set(post)         # comment → post (OK)
        post.author_fk.set(person)        # post → person (OK)

    def test_call_chaining_no_false_positive(self):
        "fk.__call__() chaining must not raise"
        person = self.person()
        post = person.post_rfk()          # person → post via __call__: OK
        comment = post.comment_rfk()      # post → comment via __call__: OK
        self.assertIsInstance(comment, self.comment)
