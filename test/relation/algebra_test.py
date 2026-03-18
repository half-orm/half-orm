#!/usr/bin/env python
#-*- coding:  utf-8 -*-

from random import sample
import string
import psycopg2
import sys
from unittest import TestCase
from datetime import date

from ..init import halftest
from half_orm import relation_errors, model
from half_orm.null import NULL

POOL = string.ascii_lowercase[10:]  # 'klmnopqrstuvwxyz' — never used in fixed 60-person data
TEST_DATE = date(1900, 1, 1)

class Test(TestCase):
    def setUp(self):
        self.pers = halftest.person_cls()
        self.post = halftest.post_cls()
        self.today = halftest.today

        c1, c2, c3, o1, o2, o3, o4 = sample(POOL, 7)

        def insert(last_name):
            self.pers(
                last_name=last_name,
                first_name=last_name,
                birth_date=TEST_DATE,
            ).ho_insert()

        insert(f'{c1}{o1}')        # set_1 only
        insert(f'{o2}{c2}')        # set_2 only
        insert(f'{c1}{c2}')        # subset_1_2 = set_1 ∩ set_2
        insert(f'{o3}{o4}{c3}')    # set_3 only

        self.universe = self.pers()
        self.empty_set = self.pers(last_name=NULL)
        self.set_1 = self.pers(last_name=('like', f'{c1}%'))
        self.comp_set_1 = self.pers(last_name=('not like', f'{c1}%'))
        self.set_2 = self.pers(last_name=('like', f'_{c2}%'))
        self.subset_1_2 = self.pers(last_name=('like', f'{c1}{c2}%'))
        self.set_3 = self.pers(last_name=('like', f'__{c3}%'))

    def tearDown(self):
        self.pers(birth_date=TEST_DATE).ho_delete(delete_all=True)

    def test_universe(self):
        "The universe contains at least the 60 seeded persons."
        self.assertGreaterEqual(self.universe.ho_count(), 60)

    def test_iand(self):
        "In-place intersection (a &= b) equals a & b."
        a = self.set_1
        b = self.set_2
        c = a & b
        a &= b
        self.assertEqual(a, c)

    def test_ior(self):
        "In-place union (a |= b) equals a | b."
        a = self.set_1
        b = self.set_2
        c = a | b
        a |= b
        self.assertEqual(a, c)

    def test_isub(self):
        "In-place difference (a -= b) equals a - b."
        a = self.set_1
        b = self.set_2
        c = a - b
        a -= b
        self.assertEqual(a, c)

    def test_xor(self):
        "Symmetric difference: a ^ b = (a | b) - (a & b)."
        a = self.set_1
        b = self.set_2
        self.assertEqual(a ^ b, (a | b) - (a & b))

    def test_ixor(self):
        "In-place symmetric difference (a ^= b) equals a ^ b."
        a = self.set_1
        b = self.set_2
        c = a ^ b
        a ^= b
        self.assertEqual(a, c)

    def test_and_1(self):
        "Intersection identity: a & b = a - (a - b)."
        a = self.set_1
        b = self.set_2
        self.assertEqual(a & b, a - ( a - b))

    def test_and_2(self):
        "Intersection identity: a & b = (a | b) - (a - b) - (b - a)."
        a = self.set_1
        b = self.set_2
        self.assertEqual(a & b, ((a | b) - (a - b) - ( b - a)))

    def test_and_3(self):
        "Idempotence of intersection: a & a = a."
        a = self.set_1
        b = self.set_1
        self.assertEqual(a & b, a)

    def test_and_4(self):
        "If ab ⊆ a, then a & ab = ab."
        a = self.set_1
        ab = self.subset_1_2
        self.assertEqual(a & ab, ab)

    def test_and_5(self):
        "If ab ⊆ b, then b & ab = ab."
        b = self.set_2
        ab = self.subset_1_2
        self.assertEqual(b & ab, ab)

    def test_and_6(self):
        "Intersection of set_1 and set_2 equals their common subset."
        a = self.set_1
        b = self.set_2
        ab = self.subset_1_2
        self.assertEqual(a & b, ab)

    def test_and_absorbing_elt(self):
        "∅ is the absorbing element of intersection: a & ∅ = ∅."
        a = self.set_1
        empty = self.empty_set
        self.assertEqual(a & empty, empty)

    def test_and_neutral_elt(self):
        "Universe is the neutral element of intersection: U & a = a."
        a = self.set_1
        universe = self.universe
        self.assertEqual(universe & a, a)

    def test_or_1(self):
        "If ab ⊆ a, then a | ab = a."
        a = self.set_1
        ab = self.subset_1_2
        self.assertEqual(a | ab, a)

    def test_or_2(self):
        "If ab ⊆ b, then b | ab = b."
        b = self.set_2
        ab = self.subset_1_2
        self.assertEqual(b | ab, b)

    def test_or_neutral_elt(self):
        "∅ is the neutral element of union: a | ∅ = a."
        a = self.set_1
        empty = self.empty_set
        self.assertEqual(a | empty, a)

    def test_or_absorbing_elt_1(self):
        "Universe is the absorbing element of union: U | a = U."
        a = self.set_1
        universe = self.universe
        self.assertEqual(universe | a, universe)

    def test_or_absorbing_elt_2(self):
        "Universe is the absorbing element of union: a | U = U."
        a = self.set_1
        universe = self.universe
        self.assertEqual(a | universe, universe)

    def test_or_absorbing_elt_3(self):
        "Union of two empty sets is empty: ∅ | ∅ = ∅."
        empty = self.empty_set
        empty1 = self.empty_set
        empty2 = self.empty_set
        self.assertEqual(empty1 | empty2, empty)

    def test_not(self):
        "Difference with empty set is identity: a - ∅ = a."
        a = self.set_1
        empty = self.empty_set
        self.assertEqual(a - empty, a)

    def test_empty(self):
        "A set minus itself is empty: a - a = ∅."
        a = self.set_1
        b = self.set_1
        empty = self.empty_set
        self.assertEqual(a - b, empty)

    def test_complementary_0(self):
        "Complement: -a equals the set of elements not in a."
        a = self.set_1
        comp_a = self.comp_set_1
        self.assertEqual(-a, comp_a)

    def test_complementary_1(self):
        "A set and its complement cover the universe: a | -a = U."
        a = self.set_1
        comp_a = self.comp_set_1
        universe = self.universe
        self.assertEqual(a | comp_a, universe)

    def test_complementary_2(self):
        "A set minus its complement is itself: a - -a = a."
        a = self.set_1
        comp_a = self.comp_set_1
        self.assertEqual(a - comp_a, a)

    def test_symetric_difference(self):
        "Symmetric difference: (a - b) | (b - a) = (a | b) - (a & b)."
        a = self.set_1
        b = self.set_2
        self.assertEqual((a - b) | (b - a), (a | b) - (a & b))

    def test_commutative_laws_1(self):
        "Commutativity of intersection: a & b = b & a."
        a = self.set_1
        b = self.set_2
        self.assertEqual(a & b, b & a)

    def test_commutative_laws_2(self):
        "Commutativity of union: a | b = b | a."
        a = self.set_1
        b = self.set_2
        self.assertEqual(a | b, b | a)

    def test_associative_laws_1(self):
        "Associativity of union: a | (b | c) = (a | b) | c."
        a = self.set_1
        b = self.set_2
        c = self.set_3
        self.assertEqual(a | (b | c), (a | b) | c)

    def test_associative_laws_2(self):
        "Associativity of intersection: a & (b & c) = (a & b) & c."
        a = self.set_1
        b = self.set_2
        c = self.set_3
        self.assertEqual(a & (b & c), (a & b) & c)

    def test_distributive_laws_1(self):
        "Distributivity of union over intersection: a | (b & c) = (a | b) & (a | c)."
        a = self.set_1
        b = self.set_2
        c = self.set_3
        self.assertEqual(a | (b & c), (a | b) & (a | c))

    def test_distributive_laws_2(self):
        "Distributivity of intersection over union: a & (b | c) = (a & b) | (a & c)."
        a = self.set_1
        b = self.set_2
        c = self.set_3
        self.assertEqual(a & (b | c), (a & b) | (a & c))

    def test_identity_laws_2(self):
        "Identity law for intersection: a & U = a."
        a = self.set_1
        universe = self.universe
        self.assertEqual(a & universe, a)

    def test_complement_laws_2(self):
        "Complement law for intersection: a & -a = ∅."
        a = self.set_1
        comp_a = self.comp_set_1
        empty = self.empty_set
        self.assertEqual(a & comp_a, empty)

    def test_complement_laws_3(self):
        "Complement law for union: a | -a = U."
        a = self.set_1
        universe = self.universe
        self.assertEqual(a | (-a), universe)

    def test_complement_laws_4(self):
        "Complement law for intersection (via unary minus): a & -a = ∅."
        a = self.set_1
        empty = self.empty_set
        self.assertEqual(a & (-a), empty)

    def test_idempotent_laws_1(self):
        "Idempotence of union: a | a = a."
        a = self.set_1
        b = self.set_1
        self.assertEqual(a | b, a)

    def test_domination_laws_2(self):
        "Domination law for intersection: a & ∅ = ∅."
        a = self.set_1
        empty = self.empty_set
        self.assertEqual(a & empty, empty)

    def test_absorption_laws_1(self):
        "Absorption law: a | (a & b) = a."
        a = self.set_1
        b = self.set_2
        self.assertEqual(a | (a & b), a)

    def test_absorption_laws_2(self):
        "Absorption law: a & (a | b) = a."
        a = self.set_1
        b = self.set_2
        self.assertEqual(a & (a | b), a)

    def test_de_morgan_s_laws_1(self):
        "De Morgan's law: -(a & b) = -a | -b."
        a = self.set_1
        b = self.set_2
        self.assertEqual((-a) | (-b), -(a & b))

    def test_de_morgan_s_laws_2(self):
        "De Morgan's law: -(a | b) = -a & -b."
        a = self.set_1
        b = self.set_2
        self.assertEqual(-(a | b), (-a) & (-b))

    def test_double_complement_law(self):
        "Double complement: -(-a) = a."
        a = self.set_1
        self.assertEqual(-(-a), a)

    def test_empty_universe_complement(self):
        "Complement of empty set is the universe: -∅ = U."
        universe = self.universe
        empty = self.empty_set
        self.assertEqual(-empty, universe)

    def test_inclusion_1_0(self):
        "Reflexivity of inclusion: a ⊆ a."
        a = self.set_1
        self.assertIn(a, a)

    def test_inclusion_1_1(self):
        "subset_1_2 is included in set_1: ab ⊆ a."
        a = self.set_1
        ab = self.subset_1_2
        self.assertIn(ab, a)

    def test_inclusion_1_2(self):
        "subset_1_2 is included in set_2: ab ⊆ b."
        b = self.set_2
        ab = self.subset_1_2
        self.assertIn(ab, b)

    def test_ab_equal_a_inter_b(self):
        "subset_1_2 equals the intersection of set_1 and set_2: ab = a & b."
        a = self.set_1
        b = self.set_2
        ab = self.subset_1_2
        self.assertEqual(ab, a & b)

    def test_inclusion_2(self):
        "Empty set is included in every set: ∅ ⊆ a."
        a = self.set_1
        empty = self.empty_set
        self.assertIn(empty, a)

    def test_inclusion_3(self):
        "Every set is included in the universe: a ⊆ U."
        a = self.set_1
        universe = self.universe
        self.assertIn(a, universe)

    def test_inclusion_4_1(self):
        "A set is included in any union containing it: a ⊆ a | b."
        a = self.set_1
        b = self.set_2
        self.assertIn(a, a | b)

    def test_inclusion_4_2(self):
        "A set is included in any union containing it: b ⊆ a | b."
        a = self.set_1
        b = self.set_2
        self.assertIn(b, a | b)

    def test_inclusion_5(self):
        "If ab ⊆ a, then ab - a = ∅."
        a = self.set_1
        ab = self.subset_1_2
        empty = self.empty_set
        self.assertEqual(ab - a, empty)

    def test_inclusion_6(self):
        "If ab ⊆ a, then -a ⊆ -ab."
        a = self.set_1
        ab = self.subset_1_2
        self.assertIn(-a, -ab)

    def test_relative_complement_1(self):
        "Relative complement: c - (a & b) = (c - a) | (c - b)."
        a = self.set_1
        b = self.set_2
        c = self.set_3
        self.assertEqual(c - (a & b), (c - a) | (c - b))

    def test_relative_complement_2(self):
        "Relative complement: c - (a | b) = (c - a) & (c - b)."
        a = self.set_1
        b = self.set_2
        c = self.set_3
        self.assertEqual(c - (a | b), (c - a) & (c - b))

    def test_relative_complement_3(self):
        "Relative complement: c - (b - a) = (a & c) | (c - b)."
        a = self.set_1
        b = self.set_2
        c = self.set_3
        self.assertEqual(c - (b - a), (a & c) | (c - b))

    def test_relative_complement_4(self):
        "Relative complement: (b - a) & c = (b & c) - a."
        a = self.set_1
        b = self.set_2
        c = self.set_3
        self.assertEqual((b - a) & c, (b & c) - a)

    def test_relative_complement_5(self):
        "Relative complement: (b - a) & c = b & (c - a)."
        a = self.set_1
        b = self.set_2
        c = self.set_3
        self.assertEqual((b - a) & c, b & (c - a))

    def test_relative_complement_6(self):
        "Relative complement: (b - a) | c = (b | c) - (a - c)."
        a = self.set_1
        b = self.set_2
        c = self.set_3
        self.assertEqual((b - a) | c, (b | c) - (a - c))

    def test_relative_complement_8(self):
        "Relative complement with empty set: ∅ - a = ∅."
        a = self.set_1
        empty = self.empty_set
        self.assertEqual(empty - a, empty)

    def test_relative_complement_10(self):
        "Relative complement via complement: b - a = -a & b."
        a = self.set_1
        b = self.set_2
        self.assertEqual(b - a, -a & b)

    def test_relative_complement_11(self):
        "Complement of relative complement: -(b - a) = a | -b."
        a = self.set_1
        b = self.set_2
        self.assertEqual(-(b - a), a | (-b))

    def test_relative_complement_12(self):
        "Relative complement with universe: U - a = -a."
        a = self.set_1
        universe = self.universe
        self.assertEqual(universe - a, -a)

    def test_relative_complement_13(self):
        "Relative complement with universe: a - U = ∅."
        a = self.set_1
        empty = self.empty_set
        universe = self.universe
        self.assertEqual(a - universe, empty)

    def test_inequality_0(self):
        "Two instances of the same filter are equal (not unequal)."
        a = self.set_1
        b = self.set_1
        self.assertFalse(a != b)

    def test_ne(self):
        "A set and its complement are not equal: a ≠ -a."
        a = self.set_1
        self.assertNotEqual(-a, a)
