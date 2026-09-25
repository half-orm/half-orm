#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for Relation.ho_read_set().

The read set names the physical relations whose contents can change a
result: a view contributes what it is defined over, a table contributes its
inheritance children, and the two compose. halftest provides both cases —
blog.event inherits blog.post, and blog.view.post_comment joins person,
comment and post.
"""

from unittest import TestCase

from halftest.actor.person import Person
from halftest.blog.post import Post
import halftest.blog.comment  # noqa: F401  — registers the Fkeys aliases


class TestInheritance(TestCase):
    """A read without ONLY returns the rows of the children too."""

    def test_parent_reads_its_children(self):
        self.assertEqual(Post().ho_read_set(), frozenset({'blog.post', 'blog.event'}))

    def test_only_excludes_the_children(self):
        restricted = Post()
        restricted.ho_only = True
        self.assertEqual(restricted.ho_read_set(), frozenset({'blog.post'}))

    def test_a_childless_relation_reads_itself(self):
        self.assertEqual(Person().ho_read_set(), frozenset({'actor.person'}))


class TestViews(TestCase):
    """A view contributes its sources, recursively, and never itself."""

    def setUp(self):
        self.view = Person()._ho_model.get_relation_class('blog.view.post_comment')

    def test_view_reaches_its_sources(self):
        read = self.view().ho_read_set()
        self.assertIn('actor.person', read)
        self.assertIn('blog.comment', read)
        self.assertIn('blog.post', read)

    def test_view_reaches_the_children_of_its_sources(self):
        # The view reads blog.post, which reads blog.event. Neither expansion
        # alone finds it.
        self.assertIn('blog.event', self.view().ho_read_set())

    def test_the_view_itself_is_absent(self):
        # A view holds no rows, so nothing is ever written to it directly.
        self.assertNotIn('blog.view.post_comment', self.view().ho_read_set())

    def test_only_on_a_view_changes_nothing(self):
        # A view has no inheritance children; ONLY is a no-op, and must not
        # cut off the children reached through its sources.
        restricted = self.view()
        restricted.ho_only = True
        self.assertEqual(restricted.ho_read_set(), self.view().ho_read_set())


class TestNavigation(TestCase):
    """Foreign-key navigation adds the relations it joins."""

    def test_navigation_adds_the_target(self):
        read = Person(last_name='Martin').posts().ho_read_set()
        self.assertEqual(read, frozenset({'actor.person', 'blog.post', 'blog.event'}))

    def test_two_hops_add_both(self):
        read = Person(last_name='Martin').commented_posts().ho_read_set()
        for table in ('actor.person', 'blog.comment', 'blog.post', 'blog.event'):
            self.assertIn(table, read)

    def test_set_operators_keep_the_read_set(self):
        self.assertEqual((Post(title='a') | Post(title='b')).ho_read_set(),
                         Post().ho_read_set())


class TestCaching(TestCase):
    """The answer depends only on the schema, so it is computed once."""

    def test_repeated_calls_agree(self):
        self.assertEqual(Post().ho_read_set(), Post().ho_read_set())

    def test_result_is_hashable_and_frozen(self):
        read = Post().ho_read_set()
        self.assertIsInstance(read, frozenset)
        hash(read)
