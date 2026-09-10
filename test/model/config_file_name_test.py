#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Model's argument is a connection file *name*, not a path, and the name it
resolves to decides which database — and as which role — the process
connects. It is checked, and a reconnect that would land on another database
is refused whether or not the file it names exists."""

from unittest import TestCase

from half_orm.model import Model, _check_config_file_name

from ..init import halftest


class TestCheckConfigFileName(TestCase):
    def test_accepts_plain_names(self):
        for name in ('halftest', 'my_db.conf', 'a_b-c', 'db1'):
            self.assertEqual(_check_config_file_name(name), name)

    def test_rejects_traversal(self):
        "os.path.join confines nothing: '..' climbs out of CONF_DIR"
        for name in ('../../etc/passwd', '../halftest', 'sub/dir', '..', '.'):
            with self.assertRaises(ValueError, msg=f'accepted: {name!r}'):
                _check_config_file_name(name)

    def test_rejects_absolute_path(self):
        "an absolute second argument makes os.path.join discard CONF_DIR entirely"
        with self.assertRaises(ValueError):
            _check_config_file_name('/etc/shadow')

    def test_rejects_empty_and_non_string(self):
        for name in ('', None, 42, ['halftest']):
            with self.assertRaises(ValueError):
                _check_config_file_name(name)

    def test_error_names_the_directory(self):
        with self.assertRaises(ValueError) as ctx:
            _check_config_file_name('/etc/shadow')
        self.assertIn('/etc/shadow', str(ctx.exception))

    def test_model_refuses_a_path(self):
        with self.assertRaises(ValueError):
            Model('../../etc/passwd')


class TestReconnectGuard(TestCase):
    """The 'can't reconnect to another database' guard used to sit inside the
    branch that found a config file. Reconnecting through a *missing* file
    skipped it: the Model silently retargeted itself, and with no file to read
    credentials from it dropped user/password/host for peer authentication."""

    def setUp(self):
        self.model = halftest.model

    def tearDown(self):
        halftest.model.reconnect()

    def test_missing_file_naming_another_database_is_refused(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.model.reconnect('some_other_database_xyz')
        self.assertIn('some_other_database_xyz', str(ctx.exception))

    def test_existing_file_naming_another_database_is_refused(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.model.reconnect('halftest_other_name_error')
        self.assertIn('another_db', str(ctx.exception))

    def test_configuration_survives_a_refused_reconnect(self):
        before = dict(self.model._dbinfo)
        with self.assertRaises(RuntimeError):
            self.model.reconnect('some_other_database_xyz')
        self.assertEqual(dict(self.model._dbinfo), before)

    def test_connection_survives_a_refused_reconnect(self):
        "the config used to be read after disconnect(), leaving the Model unusable"
        person = halftest.person_cls
        before = person().ho_count()
        with self.assertRaises(RuntimeError):
            self.model.reconnect('some_other_database_xyz')
        self.assertEqual(person().ho_count(), before)

    def test_reconnect_to_the_same_database_still_works(self):
        self.model.reconnect('halftest')
        self.assertGreater(halftest.person_cls().ho_count(), 0)
