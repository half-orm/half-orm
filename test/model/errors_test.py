#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

import os
from unittest import TestCase
from unittest.mock import patch

import psycopg

from half_orm import model_errors, model
from ..init import halftest



MISSING_SECTION_ERR=f"""Malformed config file: {os.environ['HALFORM_CONF_DIR']}/halftest_missing_database_section
Missing section: database"""
MISSING_MANDATORY_NAME=f"""Malformed config file: {os.environ['HALFORM_CONF_DIR']}/halftest_missing_mandatory_name
Missing mandatory parameter: name"""

class Test(TestCase):
    def tearDown(self):
        halftest.model.reconnect()

    # def test_missing_config_file(self):
    #     self.assertRaises(
    #         model_errors.MissingConfigFile, model.Model, "missing")

    def test_malformed_config_file_missing_database_section(self):
        "it should raise MalformedConfigFile if database section is missing"
        with self.assertRaises(model_errors.MalformedConfigFile) as exc:
            halftest.model.reconnect('halftest_missing_database_section')
        self.assertEqual(str(exc.exception), MISSING_SECTION_ERR)

    def test_malformed_config_file_missing_mandatory_name(self):
        "it should raise MalformedConfigFile if mandatory parameter name is missing"
        with self.assertRaises(model_errors.MalformedConfigFile) as exc:
            halftest.model.reconnect('halftest_missing_mandatory_name')
        self.assertEqual(str(exc.exception), MISSING_MANDATORY_NAME)

    def test_missing_schema_in_name(self):
        "it should raise a MissingSchemaInName error"
        def bad_rel_name():
            halftest.model.get_relation_class('coucou')
        self.assertRaises(model_errors.MissingSchemaInName, bad_rel_name)

    def test_can_t_reconnect_to_another_database_error(self):
        "it should raise RuntimeError if we try to reconnect to another database"
        with self.assertRaises(RuntimeError) as exc:
            halftest.model.reconnect('halftest_other_name_error')
        self.assertEqual(
            str(exc.exception), "Can't reconnect to another database: another_db != halftest")

    def test_unknown_relation(self):
        "it should raise an UnknownRelation error"
        def unknown_rel():
            halftest.model.get_relation_class('public.coucou')
        self.assertRaises(model_errors.UnknownRelation, unknown_rel)

    @patch('psycopg.connect', side_effect=psycopg.OperationalError("connection refused"))
    def test_connection_error_with_config_file(self, mock_connect):
        "it should include config file path in connection error"
        conf_dir = model.CONF_DIR
        with self.assertRaises(psycopg.OperationalError) as ctx:
            model.Model('halftest')
        error_msg = str(ctx.exception)
        self.assertIn("connection refused", error_msg)
        self.assertIn(f"Configuration file: '{conf_dir}/halftest'", error_msg)

    @patch('psycopg.connect', side_effect=psycopg.OperationalError("connection refused"))
    def test_connection_error_without_config_file(self, mock_connect):
        "it should mention missing config file and peer auth in connection error"
        conf_dir = model.CONF_DIR
        with self.assertRaises(psycopg.OperationalError) as ctx:
            model.Model('nonexistent_db_xyz')
        error_msg = str(ctx.exception)
        self.assertIn("connection refused", error_msg)
        self.assertIn(f"No configuration file found: '{conf_dir}/nonexistent_db_xyz'", error_msg)
        self.assertIn("peer authentication", error_msg)
        self.assertIn("nonexistent_db_xyz", error_msg)
