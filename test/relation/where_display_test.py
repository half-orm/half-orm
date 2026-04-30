#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for Relation.ho_where_display."""

from unittest import TestCase

from ..init import halftest


class Test(TestCase):
    def setUp(self):
        self.pers = halftest.relation("actor.person")
        self.post = halftest.relation("blog.post")

    # --- unconstrained -------------------------------------------------------

    def test_unconstrained_returns_none(self):
        self.assertIsNone(self.pers().ho_where_display())

    # --- simple leaf ---------------------------------------------------------

    def test_simple_field_constraint(self):
        result = self.pers(first_name='Alice').ho_where_display()
        self.assertIsInstance(result, dict)
        self.assertNotIn('operator', result)
        self.assertIn('joins', result)
        self.assertIn('where', result)
        self.assertIn('values', result)
        self.assertIn('Alice', result['values'])

    def test_simple_fkey_join(self):
        post = self.post()
        post.author_fk.set(self.pers(first_name='Alice'))
        result = post.ho_where_display()
        self.assertIsInstance(result, dict)
        self.assertNotIn('operator', result)
        self.assertTrue(len(result['joins']) > 0)
        self.assertIn('Alice', result['values'])

    # --- compound set operations ---------------------------------------------

    def test_or_structure(self):
        result = (self.pers(first_name='Alice') | self.pers(first_name='Bob')).ho_where_display()
        self.assertEqual(result['operator'], 'or')
        self.assertIn('left', result)
        self.assertIn('right', result)
        self.assertIn('Alice', result['left']['values'])
        self.assertIn('Bob', result['right']['values'])

    def test_and_structure(self):
        result = (self.pers(first_name='Alice') & self.pers(last_name='Martin')).ho_where_display()
        self.assertEqual(result['operator'], 'and')
        self.assertIn('left', result)
        self.assertIn('right', result)

    def test_sub_structure(self):
        result = (self.pers() - self.pers(first_name='Alice')).ho_where_display()
        self.assertEqual(result['operator'], 'and not')
        self.assertIn('left', result)
        self.assertIn('right', result)

    def test_neg_simple_leaf_embedded_in_where(self):
        "Negation of a simple leaf: NOT (...) is embedded in the where string."
        result = (-self.pers(first_name='Alice')).ho_where_display()
        self.assertNotIn('operator', result)
        self.assertIn('not', result['where'])

    def test_neg_compound_structure(self):
        "Negation of a compound operation produces {'operator': 'neg', 'operand': ...}."
        compound = self.pers(first_name='Alice') | self.pers(first_name='Bob')
        result = (-compound).ho_where_display()
        self.assertEqual(result['operator'], 'neg')
        self.assertIn('operand', result)
        self.assertEqual(result['operand']['operator'], 'or')

    # --- nested --------------------------------------------------------------

    def test_nested_compound(self):
        a = self.pers(first_name='Alice')
        b = self.pers(first_name='Bob')
        c = self.pers(first_name='Carol')
        result = ((a | b) & c).ho_where_display()
        self.assertEqual(result['operator'], 'and')
        self.assertEqual(result['left']['operator'], 'or')
        self.assertNotIn('operator', result['right'])

    # --- or with one unconstrained branch → None -----------------------------

    def test_or_unconstrained_returns_none(self):
        "A() | A(id=1) is not set (union = all rows) → None."
        result = (self.pers() | self.pers(id=1)).ho_where_display()
        self.assertIsNone(result)

    # --- constraints ---------------------------------------------------------

    def test_constraints_present(self):
        result = self.pers(first_name='Alice').ho_where_display()
        self.assertIn('constraints', result)
        self.assertIsInstance(result['constraints'], list)
        self.assertEqual(len(result['constraints']), 1)

    def test_constraints_field_comp_value(self):
        result = self.pers(first_name='Alice').ho_where_display()
        c = result['constraints'][0]
        self.assertEqual(c['field'], 'first_name')
        self.assertEqual(c['comp'], '=')
        self.assertEqual(c['value'], 'Alice')

    def test_constraints_relation_format(self):
        "relation is a (schema.table, alias) tuple."
        result = self.pers(first_name='Alice').ho_where_display()
        rel = result['constraints'][0]['relation']
        self.assertIsInstance(rel, tuple)
        self.assertEqual(len(rel), 2)
        schema_table, alias = rel
        self.assertEqual(schema_table, 'actor.person')
        self.assertTrue(alias.startswith('r'))

    def test_constraints_multiple_fields(self):
        result = self.pers(first_name='Alice', last_name='Martin').ho_where_display()
        fields = {c['field'] for c in result['constraints']}
        self.assertIn('first_name', fields)
        self.assertIn('last_name', fields)

    def test_constraints_non_equal_comp(self):
        result = self.pers(birth_date=('>', '2000-01-01')).ho_where_display()
        c = result['constraints'][0]
        self.assertEqual(c['field'], 'birth_date')
        self.assertEqual(c['comp'], '>')
        self.assertEqual(c['value'], '2000-01-01')

    def test_constraints_fkey_join_from_joined_relation(self):
        "For a FK join, constraints come from the joined relation, not the main one."
        post = self.post()
        post.author_fk.set(self.pers(first_name='Alice'))
        result = post.ho_where_display()
        self.assertEqual(len(result['constraints']), 1)
        c = result['constraints'][0]
        self.assertEqual(c['field'], 'first_name')
        self.assertEqual(c['value'], 'Alice')
        schema_table, _ = c['relation']
        self.assertEqual(schema_table, 'actor.person')

    def test_constraints_alias_in_joins(self):
        "The alias in constraints['relation'] appears in the JOIN SQL."
        post = self.post()
        post.author_fk.set(self.pers(first_name='Alice'))
        result = post.ho_where_display()
        _, alias = result['constraints'][0]['relation']
        self.assertTrue(any(alias in j for j in result['joins']))

    def test_constraints_aggregated_in_compound(self):
        "Compound nodes carry pre-aggregated constraints from all branches."
        result = (self.pers(first_name='Alice') | self.pers(first_name='Bob')).ho_where_display()
        self.assertIn('constraints', result)
        self.assertEqual(len(result['constraints']), 2)
        self.assertIn('constraints', result['left'])
        self.assertIn('constraints', result['right'])

    def test_tables_aggregated_in_compound(self):
        "Compound nodes carry the union of tables from all branches."
        result = (self.pers(first_name='Alice') | self.pers(first_name='Bob')).ho_where_display()
        self.assertIn('tables', result)
        self.assertIn('actor.person', result['tables'])

    def test_tables_aggregated_in_neg(self):
        "Neg nodes carry pre-aggregated tables from the operand."
        compound = self.pers(first_name='Alice') | self.pers(first_name='Bob')
        result = (-compound).ho_where_display()
        self.assertIn('tables', result)
        self.assertIn('actor.person', result['tables'])