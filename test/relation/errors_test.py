#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

import sys
from unittest import TestCase
from ..init import halftest
from half_orm import relation_errors, model

WRONG_FKEY_MSG = """Can't find 'this_is_a_wrong_fkey_reference'!
List of keys for Person:
 - _reverse_fkey_halftest_blog_comment_author_id
 - _reverse_fkey_halftest_blog_event_author_first_name_author_last_name_author_birth_date
 - _reverse_fkey_halftest_blog_post_author_first_name_author_last_name_author_birth_date"""

UPDATE_ALL_ERR_MSG = "Attempt to update all rows of Person without update_all being set to True!"
DELETE_ALL_ERR_MSG = "Attempt to delete all rows from Person without delete_all being set to True!"

class Test(TestCase):
    def setUp(self):
        self.pers = halftest.person_cls()

    def test_unknown_field(self):
        "it should raise AttributeError"
        with self.assertRaises(AttributeError) as cm:
            self.pers.unknown
        self.assertEqual(
            cm.exception.args[0],
            "'Person' object has no attribute 'unknown'")

    def test_unknown_attr_error(self):
        "it should raise relation_errors.UnknownAttributeError"
        with self.assertRaises(relation_errors.UnknownAttributeError):
            halftest.person_cls(lost_name='Lagaffe')

    def test_unknown_attr_error_on_insert(self):
        "it should raise relation_errors.UnknownAttributeError"
        with self.assertRaises(relation_errors.UnknownAttributeError):
            halftest.person_cls(last_name='Lagaffe').ho_insert('lost_name')

    def test_unknown_attr_error_on_select(self):
        "it should raise relation_errors.UnknownAttributeError"
        with self.assertRaises(relation_errors.UnknownAttributeError) as cm:
            list(halftest.person_cls().ho_select('lost_name', 'last_name', 'fist_name'))
        self.assertEqual(
            cm.exception.args[0],
            "ERROR! Unknown attribute: lost_name, fist_name.")

    def test_unknown_attr_error_on_update(self):
        "it should raise relation_errors.UnknownAttributeError"
        with self.assertRaises(relation_errors.UnknownAttributeError):
            halftest.person_cls(last_name='Lagaffe').ho_update('lost_name')
        with self.assertRaises(relation_errors.UnknownAttributeError):
            halftest.person_cls(last_name='Lagaffe').ho_update(lost_name="M'enfin")

    def test_unknown_attr_error_on_delete(self):
        "it should raise relation_errors.UnknownAttributeError"
        with self.assertRaises(relation_errors.UnknownAttributeError):
            halftest.person_cls(last_name='Lagaffe').ho_delete('lost_name')

    def test_is_frozen_error(self):
        "it should raise relation_errors.IsFrozenError"
        with self.assertRaises(relation_errors.IsFrozenError):
            self.pers.lost_name = 'Lagaffe'

    def test_wrong_fkey_error(self):
        "it should raise relation_errors.WrongFkeyError"
        class Person(halftest.model.get_relation_class('actor.person')):
            Fkeys = {'wrong_fk': 'this_is_a_wrong_fkey_reference'}
        with self.assertRaises(relation_errors.WrongFkeyError) as exc:
            Person()
        self.assertEqual(str(exc.exception), WRONG_FKEY_MSG)

    def test_update_all_error(self):
        "it should raise RuntimeError if update_all is not set to True."
        with self.assertRaises(RuntimeError) as exc:
            self.pers.ho_update(last_name='coucou')
        self.assertEqual(str(exc.exception), UPDATE_ALL_ERR_MSG)

    def test_delete_all_error(self):
        "it should raise RuntimeError if delete_all is not set to True."
        with self.assertRaises(RuntimeError) as exc:
            self.pers.ho_delete()
        self.assertEqual(str(exc.exception), DELETE_ALL_ERR_MSG)

    def test_write_on_view_raises(self):
        "ho_insert, ho_update, ho_delete must raise ReadOnlyRelationError on a view."
        view = halftest.blog_view_cls()
        with self.assertRaises(relation_errors.ReadOnlyRelationError):
            view.ho_insert()
        with self.assertRaises(relation_errors.ReadOnlyRelationError):
            view.ho_update(update_all=True)
        with self.assertRaises(relation_errors.ReadOnlyRelationError):
            view.ho_delete(delete_all=True)
