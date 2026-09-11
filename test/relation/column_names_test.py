#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for column-name checking and rendering.

``blog.comment`` carries a column literally named ``a = 1`` -- legitimate in
PostgreSQL, impossible as a Python attribute -- which half-orm exposes as
``column5``. It is the fixture that tells the two names apart.
"""

from unittest import TestCase

from half_orm import relation_errors

from ..init import halftest, model

ODD_COLUMN = 'a = 1'
PY_NAME = 'column5'


class TestCheckColumns(TestCase):
    """The check decides what may be interpolated into a query."""

    def setUp(self):
        self.Person = halftest.person_cls

    def test_a_real_column_passes(self):
        self.Person()._ho_check_colums('first_name', 'last_name')

    def test_an_unknown_column_is_refused(self):
        with self.assertRaises(relation_errors.UnknownAttributeError):
            self.Person()._ho_check_colums('not_a_column')

    def test_a_trailing_quote_is_refused(self):
        """Quotes used to be deleted before comparing, so this passed as
        ``first_name`` and reached the query with its quote still on."""
        with self.assertRaises(relation_errors.UnknownAttributeError):
            self.Person()._ho_check_colums('first_name"')

    def test_a_fully_quoted_name_is_accepted(self):
        """The foreign-key machinery stores its column names quoted, ready for
        a join condition, and hands that same list to ho_select."""
        self.Person()._ho_check_colums('"first_name"')

    def test_a_quoted_name_still_has_to_exist(self):
        """Unwrapping the quotes does not excuse it from the membership test."""
        with self.assertRaises(relation_errors.UnknownAttributeError):
            self.Person()._ho_check_colums('"first_name") from x --"')

    def test_a_quoted_name_renders_as_itself(self):
        query, _ = self.Person()._ho_prep_select('"first_name"')
        self.assertIn('"first_name"', query)
        self.assertNotIn('as "first_name"', query)

    def test_the_offender_is_named(self):
        """`Unknown attribute: .` named nothing: the report was built from the
        stripped set while the arguments kept their quotes."""
        with self.assertRaises(relation_errors.UnknownAttributeError) as ctx:
            self.Person()._ho_check_colums('bad"name')
        self.assertIn('bad"name', str(ctx.exception))

    def test_every_offender_is_named(self):
        with self.assertRaises(relation_errors.UnknownAttributeError) as ctx:
            self.Person()._ho_check_colums('first_name', 'nope_a', 'nope_b')
        self.assertIn('nope_a', str(ctx.exception))
        self.assertIn('nope_b', str(ctx.exception))

    def test_a_non_string_is_reported_not_crashed_on(self):
        """`elt.replace` raised AttributeError from inside the check."""
        for value in (42, None, ['first_name']):
            with self.subTest(value=value):
                with self.assertRaises(relation_errors.UnknownAttributeError):
                    self.Person()._ho_check_colums(value)


class TestColumnRendering(TestCase):
    """What the check lets through still has to be rendered correctly."""

    def setUp(self):
        self.Person = halftest.person_cls
        self.Comment = model.get_relation_class('blog.comment')

    def test_names_are_quoted(self):
        query, _ = self.Person()._ho_prep_select('first_name')
        self.assertIn('"first_name"', query)

    def test_renamed_column_resolves_to_its_real_name(self):
        """`column5` is half-orm's name for it; PostgreSQL has never heard of
        it, and used to answer `column column5 does not exist`."""
        query, _ = self.Comment()._ho_prep_select(PY_NAME)
        self.assertIn(f'"{ODD_COLUMN}"', query)
        self.assertNotIn(f'.{PY_NAME}', query)

    def test_renamed_column_is_labelled_back(self):
        """A caller who asked for `column5` should read row['column5']."""
        query, _ = self.Comment()._ho_prep_select(PY_NAME)
        self.assertIn(f'as "{PY_NAME}"', query)

    def test_an_ordinary_column_is_not_labelled(self):
        """Only a renamed column needs a label; the rest stay unadorned."""
        query, _ = self.Comment()._ho_prep_select('content')
        self.assertNotIn('as "content"', query)

    def test_returning_resolves_the_real_name(self):
        query, _ = self.Comment(content='x')._ho_prep_insert(PY_NAME)
        returning = query.split('returning')[-1]
        self.assertIn(f'"{ODD_COLUMN}"', returning)

    def test_returning_star_is_left_alone(self):
        query, _ = self.Comment(content='x')._ho_prep_insert('*')
        self.assertIn('returning *', query)

    def test_where_already_used_the_real_name(self):
        """Unchanged: this path was already correct, and pins it."""
        query, _ = self.Comment(**{PY_NAME: 'x'})._ho_prep_select()
        self.assertIn(f'"{ODD_COLUMN}"', query)


class TestRenamedColumnRoundTrip(TestCase):
    """Insert, read, update and delete through the renamed column."""

    def setUp(self):
        self.Comment = model.get_relation_class('blog.comment')
        Post = model.get_relation_class('blog.post')
        person = next(iter(halftest.person_cls().ho_select(
            'first_name', 'last_name', 'birth_date', 'id')))
        self.person_id = person['id']
        self.post = Post(
            title='tmp-column-names', content='x',
            author_first_name=person['first_name'],
            author_last_name=person['last_name'],
            author_birth_date=person['birth_date']).ho_insert('id')
        self.Post = Post

    def tearDown(self):
        self.Comment(post_id=self.post['id']).ho_delete(delete_all=True)
        self.Post(title='tmp-column-names').ho_delete(delete_all=True)

    def _insert(self, value):
        return self.Comment(
            content='probe', post_id=self.post['id'],
            author_id=self.person_id, **{PY_NAME: value}).ho_insert('id', PY_NAME)

    def test_insert_returning_uses_the_python_name_as_key(self):
        row = self._insert('v1')
        self.assertEqual(row[PY_NAME], 'v1')

    def test_select_reads_it_back(self):
        row = self._insert('v2')
        read = list(self.Comment(id=row['id']).ho_select(PY_NAME, 'content'))
        self.assertEqual(read[0][PY_NAME], 'v2')
        self.assertEqual(read[0]['content'], 'probe')

    def test_update_then_select(self):
        row = self._insert('v3')
        self.Comment(id=row['id']).ho_update(**{PY_NAME: 'v3-bis'})
        read = list(self.Comment(id=row['id']).ho_select(PY_NAME))
        self.assertEqual(read[0][PY_NAME], 'v3-bis')

    def test_delete_returning(self):
        row = self._insert('v4')
        deleted = self.Comment(id=row['id']).ho_delete(PY_NAME)
        self.assertEqual(deleted[0][PY_NAME], 'v4')
