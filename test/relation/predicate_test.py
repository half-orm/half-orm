#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Predicate-level tests for halftest business logic methods.

These tests verify the *structure* of the predicates built by business
methods — which tables are reached, which fields are constrained, which
values are carried — without inserting any data or executing SELECT queries.
"""

from unittest import TestCase

from half_orm.testing import (
    assertConstraintsMatch, assertInvolvesTables, assertSamePredicate,
    assertTablePath,
    constraint_count, constraint_tables, constraint_values, constraints_match,
    find_constraints, is_unconstrained, traversed_tables,
)
from halftest.actor.person import Person
from halftest.blog.post import Post


class TestPersonPosts(TestCase):
    """Person.posts() → all posts by this person."""

    def test_involves_person_table(self):
        self.assertIn('actor.person', constraint_tables(
            Person(last_name='Martin').posts().ho_where_display()))

    def test_carries_last_name(self):
        self.assertTrue(constraints_match(
            Person(last_name='Martin').posts(),
            table='actor.person', field='last_name', comp='=', value='Martin'))

    def test_unconstrained_person_gives_none(self):
        self.assertIsNone(Person().posts().ho_where_display())


class TestPersonCommentedPosts(TestCase):
    """Person.commented_posts() → posts this person has commented on."""

    def test_person_constraint_propagates(self):
        self.assertTrue(constraints_match(
            Person(last_name='Martin').commented_posts(),
            table='actor.person', field='last_name', comp='=', value='Martin'))


class TestPostCommenters(TestCase):
    """Post.commenters() → people who commented on this post."""

    def test_post_title_constraint_propagates(self):
        self.assertTrue(constraints_match(
            Post(title='Hello').commenters(),
            table='blog.post', field='title', comp='=', value='Hello'))


class TestPostComments(TestCase):
    """Post.comments() → all comments on this post."""

    def test_post_title_constraint_propagates(self):
        self.assertTrue(constraints_match(
            Post(title='Hello').comments(),
            table='blog.post', field='title', comp='=', value='Hello'))


class TestConstraintsMatch(TestCase):
    """constraints_match() behaviour."""

    def test_non_equal_comp(self):
        self.assertTrue(constraints_match(
            Person(birth_date=('>', '2000-01-01')).posts(),
            field='birth_date', comp='>', value='2000-01-01'))

    def test_no_match_returns_false(self):
        self.assertFalse(constraints_match(
            Person(last_name='Martin').posts(),
            table='blog.comment'))

    def test_partial_criteria(self):
        "Omitting some criteria widens the search."
        self.assertTrue(constraints_match(
            Person(last_name='Martin').posts(),
            value='Martin'))


class TestIsUnconstrained(TestCase):
    """is_unconstrained() behaviour."""

    def test_unconstrained_relation(self):
        self.assertTrue(is_unconstrained(Person()))

    def test_constrained_relation(self):
        self.assertFalse(is_unconstrained(Person(last_name='Martin')))

    def test_unconstrained_traversal(self):
        "Traversal from an unconstrained relation is itself unconstrained."
        self.assertTrue(is_unconstrained(Person().posts()))


class TestAssertInvolvesTables(TestCase):
    """assertInvolvesTables() behaviour."""

    def test_single_table(self):
        self.assertTrue(assertInvolvesTables(
            Person(last_name='Martin').posts(),
            'actor.person'))

    def test_full_path(self):
        "commenters() traverses post → comment → person even if only post is constrained."
        self.assertTrue(assertInvolvesTables(
            Post(title='Hello').commenters(),
            'blog.post', 'blog.comment', 'actor.person'))

    def test_raises_on_absent_table(self):
        with self.assertRaises(AssertionError) as ctx:
            assertInvolvesTables(Person(last_name='Martin').posts(), 'blog.comment')
        msg = str(ctx.exception)
        self.assertIn('blog.comment', msg)
        self.assertIn('Found', msg)

    def test_raises_on_partial_match(self):
        "All tables must be present — one absent table raises."
        with self.assertRaises(AssertionError):
            assertInvolvesTables(
                Person(last_name='Martin').posts(),
                'actor.person', 'blog.comment')

    def test_custom_message(self):
        with self.assertRaises(AssertionError) as ctx:
            assertInvolvesTables(
                Person(last_name='Martin').posts(),
                'blog.comment',
                msg='path does not reach comment')
        self.assertEqual(str(ctx.exception), 'path does not reach comment')

    def test_traversed_tables_vs_constraint_tables(self):
        "traversed_tables includes join-only tables; constraint_tables does not."
        rel = Post(title='Hello').commenters()
        node = rel.ho_where_display()
        all_t = traversed_tables(node)
        constrained_t = constraint_tables(node)
        self.assertIn('blog.comment', all_t)
        self.assertNotIn('blog.comment', constrained_t)


class TestConstraintCount(TestCase):
    """constraint_count() behaviour."""

    def test_total_count(self):
        self.assertEqual(constraint_count(Person(last_name='Martin').posts()), 1)

    def test_count_by_table(self):
        self.assertEqual(
            constraint_count(Person(last_name='Martin').posts(), table='actor.person'), 1)

    def test_count_absent_table(self):
        self.assertEqual(
            constraint_count(Person(last_name='Martin').posts(), table='blog.comment'), 0)

    def test_count_multi_table_path(self):
        "commenters() goes post → comment → person: three tables, one constraint each."
        total = constraint_count(Post(title='Hello').commenters())
        self.assertEqual(total, 1)


class TestAssertConstraintsMatch(TestCase):
    """assertConstraintsMatch() behaviour."""

    def test_passes_on_match(self):
        assertConstraintsMatch(
            Person(last_name='Martin').posts(),
            table='actor.person', field='last_name', value='Martin')

    def test_raises_on_no_match(self):
        with self.assertRaises(AssertionError) as ctx:
            assertConstraintsMatch(
                Person(last_name='Martin').posts(),
                table='blog.comment')
        self.assertIn('blog.comment', str(ctx.exception))

    def test_custom_message(self):
        with self.assertRaises(AssertionError) as ctx:
            assertConstraintsMatch(
                Person(last_name='Martin').posts(),
                table='blog.comment',
                msg='post constraint missing')
        self.assertEqual(str(ctx.exception), 'post constraint missing')

    def test_diagnostic_lists_found_constraints(self):
        "Error message shows what was actually found."
        with self.assertRaises(AssertionError) as ctx:
            assertConstraintsMatch(
                Person(last_name='Martin').posts(),
                field='title')
        self.assertIn('Found', str(ctx.exception))


class TestAssertSamePredicate(TestCase):
    """assertSamePredicate() behaviour."""

    def test_identical_predicates_pass(self):
        "Same relation constructed twice gives the same predicate."
        assertSamePredicate(
            Person(last_name='Martin').posts(),
            Person(last_name='Martin').posts())

    def test_different_values_fail(self):
        with self.assertRaises(AssertionError):
            assertSamePredicate(
                Person(last_name='Martin').posts(),
                Person(last_name='Dupont').posts())

    def test_different_fields_fail(self):
        with self.assertRaises(AssertionError):
            assertSamePredicate(
                Person(last_name='Martin').posts(),
                Person(first_name='Martin').posts())

    def test_or_is_commutative(self):
        "A | B and B | A produce the same canonical predicate."
        a = Person(last_name='Martin')
        b = Person(last_name='Dupont')
        assertSamePredicate(a | b, b | a)

    def test_and_is_commutative(self):
        "A & B and B & A produce the same canonical predicate."
        a = Person(last_name='Martin')
        b = Person(first_name='Jean')
        assertSamePredicate(a & b, b & a)

    def test_and_not_is_not_commutative(self):
        "A - B and B - A are structurally different."
        a = Person(last_name='Martin')
        b = Person(first_name='Jean')
        with self.assertRaises(AssertionError):
            assertSamePredicate(a - b, b - a)

    def test_custom_message(self):
        with self.assertRaises(AssertionError) as ctx:
            assertSamePredicate(
                Person(last_name='Martin').posts(),
                Person(last_name='Dupont').posts(),
                msg='delegation broke')
        self.assertEqual(str(ctx.exception), 'delegation broke')


class TestAssertTablePath(TestCase):
    """assertTablePath() behaviour."""

    def test_simple_fk_path(self):
        "posts() goes person → post in navigation order."
        assertTablePath(
            Person(last_name='Martin').posts(),
            'actor.person', 'blog.post')

    def test_two_hop_path(self):
        "commenters() traverses post → comment → person."
        assertTablePath(
            Post(title='Hello').commenters(),
            'blog.post', 'blog.comment', 'actor.person')

    def test_wrong_order_fails(self):
        with self.assertRaises(AssertionError) as ctx:
            assertTablePath(
                Post(title='Hello').commenters(),
                'actor.person', 'blog.comment', 'blog.post')
        self.assertIn('expected', str(ctx.exception))
        self.assertIn('found', str(ctx.exception))

    def test_missing_table_fails(self):
        with self.assertRaises(AssertionError):
            assertTablePath(
                Post(title='Hello').commenters(),
                'blog.post', 'actor.person')

    def test_raises_on_compound(self):
        a = Person(last_name='Martin')
        b = Person(last_name='Dupont')
        with self.assertRaises(AssertionError) as ctx:
            assertTablePath(a | b, 'actor.person')
        self.assertIn('compound', str(ctx.exception))

    def test_raises_on_unconstrained(self):
        with self.assertRaises(AssertionError) as ctx:
            assertTablePath(Person().posts(), 'actor.person', 'blog.post')
        self.assertIn('unconstrained', str(ctx.exception))

    def test_custom_message(self):
        with self.assertRaises(AssertionError) as ctx:
            assertTablePath(
                Post(title='Hello').commenters(),
                'blog.post', 'actor.person',
                msg='wrong traversal path')
        self.assertEqual(str(ctx.exception), 'wrong traversal path')