#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for DELETE and UPDATE operations performed via FK navigation.

The critical invariant is:
  - Constraints carried by _ho_join_to (FK navigation) MUST appear in the
    generated SQL for DELETE and UPDATE — never silently dropped.
  - When the join matches 0 rows the operation must affect 0 rows, not ALL rows.
"""

from unittest import TestCase

from ..init import halftest


class TestFKDelete(TestCase):
    """DELETE safety and correctness via FK navigation."""

    def setUp(self):
        self.today = halftest.today
        # Two distinct authors whose last_name allows targeted cleanup.
        self.author_a = halftest.person_cls(
            last_name='fk_write_tester_A',
            first_name='test',
            birth_date=self.today,
        ).ho_insert()
        self.author_b = halftest.person_cls(
            last_name='fk_write_tester_B',
            first_name='test',
            birth_date=self.today,
        ).ho_insert()
        # One post per author.
        self.post_a = halftest.post_cls(
            title='Post by A',
            content='content A',
            author_first_name='test',
            author_last_name='fk_write_tester_A',
            author_birth_date=self.today,
        ).ho_insert()
        self.post_b = halftest.post_cls(
            title='Post by B',
            content='content B',
            author_first_name='test',
            author_last_name='fk_write_tester_B',
            author_birth_date=self.today,
        ).ho_insert()

    def tearDown(self):
        halftest.person_cls(last_name=('like', 'fk_write_tester%')).ho_delete()

    # ------------------------------------------------------------------
    # SQL shape
    # ------------------------------------------------------------------

    def test_delete_via_fk_sql_uses_subquery(self):
        "DELETE through FK navigation must use IN (SELECT ...) not fkey.values()"
        query, _ = (
            halftest.person_cls(last_name='fk_write_tester_A')
            .post_rfk()
            ._ho_prep_delete()
        )
        self.assertIn(' in (', query.lower())
        self.assertIn('select', query.lower())

    # ------------------------------------------------------------------
    # Correctness
    # ------------------------------------------------------------------

    def test_delete_via_fk_deletes_only_matched_rows(self):
        "Only posts by author A must be deleted when navigating via FK from A"
        total_before = halftest.post_cls().ho_count()
        halftest.person_cls(last_name='fk_write_tester_A').post_rfk().ho_delete()
        total_after = halftest.post_cls().ho_count()
        self.assertEqual(total_before - total_after, 1)
        # post_b must still exist
        self.assertEqual(halftest.post_cls(id=self.post_b['id']).ho_count(), 1)

    # ------------------------------------------------------------------
    # Safety (the critical regression test for the security bug)
    # ------------------------------------------------------------------

    def test_delete_via_fk_no_match_deletes_nothing(self):
        """FK navigation matching 0 rows must not delete any rows.

        With the old fkey.values() mechanism, an empty result caused the WHERE
        clause to be silently dropped, producing DELETE FROM table with no
        predicate — wiping the entire table.
        """
        total_before = halftest.post_cls().ho_count()
        # No person with this last_name exists, so the subquery returns nothing.
        halftest.person_cls(
            last_name='fk_write_tester_NONEXISTENT'
        ).post_rfk().ho_delete()
        total_after = halftest.post_cls().ho_count()
        self.assertEqual(total_before, total_after,
            "DELETE via FK navigation with empty join result must affect 0 rows")


class TestFKUpdate(TestCase):
    """UPDATE safety and correctness via FK navigation."""

    def setUp(self):
        self.today = halftest.today
        self.author_a = halftest.person_cls(
            last_name='fk_write_tester_A',
            first_name='test',
            birth_date=self.today,
        ).ho_insert()
        self.author_b = halftest.person_cls(
            last_name='fk_write_tester_B',
            first_name='test',
            birth_date=self.today,
        ).ho_insert()
        self.post_a = halftest.post_cls(
            title='Post by A',
            content='content A',
            author_first_name='test',
            author_last_name='fk_write_tester_A',
            author_birth_date=self.today,
        ).ho_insert()
        self.post_b = halftest.post_cls(
            title='Post by B',
            content='content B',
            author_first_name='test',
            author_last_name='fk_write_tester_B',
            author_birth_date=self.today,
        ).ho_insert()

    def tearDown(self):
        halftest.person_cls(last_name=('like', 'fk_write_tester%')).ho_delete()

    # ------------------------------------------------------------------
    # SQL shape
    # ------------------------------------------------------------------

    def test_update_via_fk_sql_uses_subquery(self):
        "UPDATE through FK navigation must use IN (SELECT ...) not fkey.values()"
        prep = (
            halftest.person_cls(last_name='fk_write_tester_A')
            .post_rfk()
            ._ho_prep_update(title='x')
        )
        self.assertIsNotNone(prep)
        query, _, _ = prep
        self.assertIn(' in (', query.lower())
        self.assertIn('select', query.lower())

    # ------------------------------------------------------------------
    # Correctness
    # ------------------------------------------------------------------

    def test_update_via_fk_updates_only_matched_rows(self):
        "Only posts by author A must be updated when navigating via FK from A"
        halftest.person_cls(last_name='fk_write_tester_A').post_rfk().ho_update(
            title='Updated')
        updated = next(halftest.post_cls(id=self.post_a['id']).ho_select('title'))
        self.assertEqual(updated['title'], 'Updated')
        unchanged = next(halftest.post_cls(id=self.post_b['id']).ho_select('title'))
        self.assertEqual(unchanged['title'], 'Post by B')

    # ------------------------------------------------------------------
    # Safety
    # ------------------------------------------------------------------

    def test_update_via_fk_no_match_updates_nothing(self):
        """FK navigation matching 0 rows must not update any rows.

        With the old fkey.values() mechanism, an empty result caused the WHERE
        clause to be silently dropped, producing UPDATE table SET ... with no
        predicate — overwriting the entire table.
        """
        halftest.person_cls(
            last_name='fk_write_tester_NONEXISTENT'
        ).post_rfk().ho_update(title='Should not happen')
        unchanged = next(halftest.post_cls(id=self.post_b['id']).ho_select('title'))
        self.assertEqual(unchanged['title'], 'Post by B',
            "UPDATE via FK navigation with empty join result must affect 0 rows")