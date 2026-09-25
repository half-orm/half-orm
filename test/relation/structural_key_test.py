#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for Relation.ho_structural_key().

The key identifies how a question was asked, not what it returns. These
tests verify that it is hashable, stable, canonical for the commutative
operators, and that it never conflates two different relations. No data is
inserted and no SELECT is executed.
"""

from unittest import TestCase

from half_orm.testing import assertSamePredicate
from halftest.actor.person import Person
from halftest.blog.post import Post


class TestHashable(TestCase):
    """A Relation is unhashable; its structural key is not."""

    def test_relation_itself_is_unhashable(self):
        with self.assertRaises(TypeError):
            hash(Person(last_name='Martin'))

    def test_key_is_hashable(self):
        hash(Person(last_name='Martin').ho_structural_key())

    def test_key_works_as_dict_key(self):
        cache = {Person(last_name='Martin').ho_structural_key(): 'rows'}
        self.assertEqual(cache[Person(last_name='Martin').ho_structural_key()], 'rows')

    def test_key_works_as_set_member(self):
        seen = {Person(last_name='Martin').ho_structural_key()}
        self.assertIn(Person(last_name='Martin').ho_structural_key(), seen)
        self.assertNotIn(Person(last_name='Dupont').ho_structural_key(), seen)


class TestStability(TestCase):
    """The key is a pure function of the predicate, not of the instance."""

    def test_same_question_same_key(self):
        self.assertEqual(
            Person(last_name='Martin').ho_structural_key(),
            Person(last_name='Martin').ho_structural_key())

    def test_repeated_calls_agree(self):
        rel = Person(last_name='Martin').posts()
        self.assertEqual(rel.ho_structural_key(), rel.ho_structural_key())

    def test_independent_of_instance_alias(self):
        # Two separately built objects carry different r{ho_id} aliases.
        left, right = Person(last_name='Martin'), Person(last_name='Martin')
        self.assertNotEqual(left.ho_id, right.ho_id)
        self.assertEqual(left.ho_structural_key(), right.ho_structural_key())


class TestCanonicalisation(TestCase):
    """Commutative operators are normalised; non-commutative ones are not."""

    def setUp(self):
        self.a = Person(last_name='Martin')
        self.b = Person(first_name='Jo')

    def test_or_is_commutative(self):
        self.assertEqual((self.a | self.b).ho_structural_key(),
                         (self.b | self.a).ho_structural_key())

    def test_and_is_commutative(self):
        self.assertEqual((self.a & self.b).ho_structural_key(),
                         (self.b & self.a).ho_structural_key())

    def test_sub_is_not_commutative(self):
        self.assertNotEqual((self.a - self.b).ho_structural_key(),
                            (self.b - self.a).ho_structural_key())

    def test_negation_changes_the_key(self):
        self.assertNotEqual(self.a.ho_structural_key(), (-self.a).ho_structural_key())


class TestDiscrimination(TestCase):
    """Different questions get different keys."""

    def test_different_values(self):
        self.assertNotEqual(Person(last_name='Martin').ho_structural_key(),
                            Person(last_name='Dupont').ho_structural_key())

    def test_different_fields(self):
        self.assertNotEqual(Person(last_name='Martin').ho_structural_key(),
                            Person(first_name='Martin').ho_structural_key())

    def test_different_comparators(self):
        self.assertNotEqual(Person(last_name='Martin').ho_structural_key(),
                            Person(last_name=('like', 'Martin')).ho_structural_key())

    def test_fk_navigation_changes_the_key(self):
        person = Person(last_name='Martin')
        self.assertNotEqual(person.ho_structural_key(),
                            person.posts().ho_structural_key())

    def test_only_changes_the_key(self):
        # ONLY excludes the inheritance children, so it selects a different
        # set: blog.event inherits blog.post.
        plain = Post(title='x')
        restricted = Post(title='x')
        restricted.ho_only = True
        self.assertNotEqual(plain.ho_structural_key(),
                            restricted.ho_structural_key())

    def test_only_changes_the_key_of_a_compound(self):
        plain = Post(title='x') | Post(title='y')
        restricted = Post(title='x') | Post(title='y')
        restricted.ho_only = True
        self.assertNotEqual(plain.ho_structural_key(),
                            restricted.ho_structural_key())

    def test_only_on_an_operand_is_ignored(self):
        # ONLY applies to the relation being read. Set on an operand it never
        # reaches the query, so it must not reach the key either.
        operand = Post(title='x')
        operand.ho_only = True
        self.assertEqual((operand | Post(title='y')).ho_structural_key(),
                         (Post(title='x') | Post(title='y')).ho_structural_key())

    def test_unconstrained_relations_on_different_tables_differ(self):
        # Both have an empty predicate; only the relation tells them apart.
        self.assertIsNone(Person().ho_where_display())
        self.assertIsNone(Post().ho_where_display())
        self.assertNotEqual(Person().ho_structural_key(), Post().ho_structural_key())

    def test_unconstrained_key_names_the_relation(self):
        (fqrn, only), predicate = Person().ho_structural_key()
        self.assertEqual(fqrn[1:], ('actor', 'person'))
        self.assertFalse(only)
        self.assertIsNone(predicate)


class TestAgreesWithAssertSamePredicate(TestCase):
    """The key and the test helper are the same notion, by construction."""

    def test_equal_keys_pass_the_assertion(self):
        assertSamePredicate(Person(last_name='Martin'), Person(last_name='Martin'))

    def test_unconstrained_relations_on_different_tables_are_rejected(self):
        with self.assertRaises(AssertionError):
            assertSamePredicate(Person(), Post())

    def test_a_predicate_does_not_equal_its_complement(self):
        rel = Person(last_name='Martin')
        with self.assertRaises(AssertionError):
            assertSamePredicate(rel, -rel)

    def test_negated_compound_and_negated_leaf_agree(self):
        a, b = Person(last_name='Martin'), Person(first_name='Jo')
        self.assertNotEqual((a | b).ho_structural_key(),
                            (-(a | b)).ho_structural_key())

    def test_helper_and_key_agree_on_commutativity(self):
        a, b = Person(last_name='Martin'), Person(first_name='Jo')
        assertSamePredicate(a | b, b | a)
        self.assertEqual((a | b).ho_structural_key(), (b | a).ho_structural_key())
