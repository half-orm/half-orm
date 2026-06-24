import contextlib
import io
import os
import re
import sys
import pytest
from unittest import TestCase, skip
from half_orm import utils


cur_dir = os.path.abspath(os.path.dirname(__file__))
rwd_test_file = os.path.join(cur_dir, 'rwd_test_file')

data = """coucou
c'est un test
"""

datalines = ['coucou\n', "c'est un test\n"]
class Test(TestCase):
    def tearDown(self):
        if os.path.exists(rwd_test_file):
            os.remove(rwd_test_file)

    def test_check_attribute_name(self):
        "it return errors"
        self.assertEqual(
            utils.check_attribute_name("class"), '"class" is a reserved keyword in Python.')
        self.assertEqual(
            utils.check_attribute_name(
                "not a valid variable"),
                '"not a valid variable" is not a valid identifier in Python.')

    def test_file_utils(self):
        self.assertFalse(os.path.exists(rwd_test_file))
        utils.write(rwd_test_file, data)
        self.assertTrue(os.path.exists(rwd_test_file))
        self.assertEqual(utils.read(rwd_test_file), data)
        self.assertEqual(utils.readlines(rwd_test_file), datalines)
        utils.write(rwd_test_file, data, "a+")
        self.assertEqual(utils.read(rwd_test_file), data + data)

    def test_green(self):
        self.assertEqual(utils.Color.green('coucou'), '\x1b[1;32mcoucou\x1b[0m')

    def test_blue(self):
        self.assertEqual(utils.Color.blue('coucou'), '\x1b[1;34mcoucou\x1b[0m')

    def test_warning(self):
        f = io.StringIO()
        with contextlib.redirect_stderr(f):
            utils.warning('coucou')
            self.assertEqual(f.getvalue(), '\x1b[1mhalf-orm WARNING\x1b[0m: coucou')

    def test_error_exit_code(self):
        with self.assertRaises(SystemExit) as cm:
            utils.error('coucou', 42)
        self.assertEqual(cm.exception.code, 42)

    def test_error_show_caller(self):
        f = io.StringIO()
        with contextlib.redirect_stderr(f):
            utils.error('boom', show_caller=True)
        output = f.getvalue()
        self.assertIn('\x1b[1mhalf-orm ERROR\x1b[0m:', output)
        self.assertIn('misc_test.py', output)
        self.assertIn('test_error_show_caller', output)
        self.assertIn("utils.error('boom', show_caller=True)", output)

    def test_warning_show_caller(self):
        f = io.StringIO()
        with contextlib.redirect_stderr(f):
            utils.warning('coucou', show_caller=True)
        output = f.getvalue()
        self.assertIn('\x1b[1mhalf-orm WARNING\x1b[0m: coucou', output)
        self.assertIn('misc_test.py', output)
        self.assertIn('test_warning_show_caller', output)
        self.assertIn("utils.warning('coucou', show_caller=True)", output)
