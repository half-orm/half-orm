#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Boolean connection-file flags, and the redaction of query parameters.

`production` has no security meaning inside half_orm — parameters are never
logged, in any mode. It records the environment a connection belongs to, and
half_orm_dev reads it through Model._production_mode to make a server
read-only, so its default must stay False."""

from unittest import TestCase

from half_orm import model_errors
from half_orm.model import _config_bool, _describe_values


class TestConfigBool(TestCase):
    def test_recognized_spellings(self):
        "ConfigParser hands back strings; every documented spelling must work"
        for raw, expected in (
                ('True', True), ('true', True), ('TRUE', True),
                ('yes', True), ('on', True), ('1', True),
                ('False', False), ('false', False), ('FALSE', False),
                ('no', False), ('off', False), ('0', False)):
            self.assertIs(_config_bool({'k': raw}, 'k', None, 'f'), expected,
                          msg=f'{raw!r}')

    def test_lowercase_false_is_false(self):
        "the bug this replaces: only the exact string 'False' was honoured"
        self.assertIs(_config_bool({'k': 'false'}, 'k', True, 'f'), False)

    def test_surrounding_whitespace_ignored(self):
        self.assertIs(_config_bool({'k': '  true  '}, 'k', False, 'f'), True)

    def test_real_booleans_pass_through(self):
        "the peer-authentication fallback builds a plain dict, not a section"
        self.assertIs(_config_bool({'k': True}, 'k', False, 'f'), True)
        self.assertIs(_config_bool({'k': False}, 'k', True, 'f'), False)

    def test_missing_key_returns_default(self):
        self.assertIs(_config_bool({}, 'k', False, 'f'), False)
        self.assertIs(_config_bool({}, 'k', True, 'f'), True)

    def test_unparsable_value_raises(self):
        with self.assertRaises(model_errors.MalformedConfigFile) as ctx:
            _config_bool({'production': 'maybe'}, 'production', False, '/etc/half_orm/db')
        self.assertIn('production', str(ctx.exception))
        self.assertIn('maybe', str(ctx.exception))


class TestDescribeValues(TestCase):
    "A failing query must report the shape of its parameters, never their content."

    def test_secret_never_appears(self):
        described = _describe_values(('SUPER_SECRET_TOKEN',))
        self.assertNotIn('SUPER_SECRET_TOKEN', described)
        self.assertEqual(described, '(str[18])')

    def test_mixed_types(self):
        self.assertEqual(_describe_values(('abc', 42, None)), '(str[3], int, NULL)')

    def test_none(self):
        self.assertEqual(_describe_values(None), 'none')

    def test_bare_value_is_wrapped(self):
        self.assertEqual(_describe_values('abcd'), '(str[4])')

    def test_sized_containers_report_their_length(self):
        self.assertEqual(_describe_values(({'a': 1},)), '(dict[1])')
        self.assertEqual(_describe_values(([1, 2, 3],)), '(list[3])')

    def test_unsized_values_report_their_type_only(self):
        self.assertEqual(_describe_values((1.5,)), '(float)')


class TestErrorOutputRedaction(TestCase):
    "End-to-end: the stderr written by a failing query must not carry values."

    def test_failing_query_does_not_log_its_parameters(self):
        import contextlib
        import io

        import psycopg

        from ..init import halftest

        secret = 'SUPER_SECRET_TOKEN'
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(psycopg.Error):
                halftest.model.execute_query(
                    'select * from no_such_table where x = %s', (secret,))
        written = err.getvalue()
        self.assertIn('Query execution failed', written)
        self.assertNotIn(secret, written)
        self.assertIn(f'str[{len(secret)}]', written)
