"""Tests for SQL trace functionality"""

from unittest import TestCase
from io import StringIO
import sys
from ..init import model
from half_orm import utils

PERSON = 'actor.person'


class TestSqlTrace(TestCase):
    """Test suite for SQL trace mode"""

    def setUp(self):
        """Setup test fixtures"""
        self.original_sql_trace = model.sql_trace

    def tearDown(self):
        """Restore original state"""
        model.sql_trace = self.original_sql_trace

    def test_sql_trace_property_default_false(self):
        """Test that sql_trace is False by default"""
        # Create a fresh model to ensure clean state
        from half_orm.model import Model
        test_model = Model('halftest')
        self.assertFalse(test_model.sql_trace)

    def test_sql_trace_property_setter(self):
        """Test that sql_trace property can be set"""
        model.sql_trace = True
        self.assertTrue(model.sql_trace)
        model.sql_trace = False
        self.assertFalse(model.sql_trace)

    def test_get_caller_info_function(self):
        """Test the utils.get_caller_info function"""
        def test_function():
            return utils.get_caller_info(skip_frames=1)

        caller_info = test_function()

        # Verify that caller_info contains expected keys
        self.assertIsNotNone(caller_info)
        self.assertIn('filename', caller_info)
        self.assertIn('lineno', caller_info)
        self.assertIn('function', caller_info)
        self.assertIn('code_context', caller_info)

        # Verify that the function name is 'test_function' (skip_frames=1 means immediate caller)
        self.assertEqual(caller_info['function'], 'test_function')

    def test_sql_trace_output_format(self):
        """Test that SQL trace outputs caller information when enabled"""
        # Enable SQL trace
        model.sql_trace = True

        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            # Execute a query that will trigger the trace
            Person = model.get_relation_class(PERSON)
            person = Person()
            list(person.ho_select(limit=1))

            # Get the output
            output = captured_output.getvalue()

            # Verify that trace information is present
            self.assertIn('SQL TRACE', output)
            self.assertIn('File:', output)
            self.assertIn('Function:', output)
            self.assertIn('Code:', output)

            # Verify that SQL query is also present (from execute_query)
            self.assertIn('select', output)

        finally:
            # Restore stdout
            sys.stdout = sys.__stdout__
            model.sql_trace = False

    def test_sql_trace_disabled_no_output(self):
        """Test that no trace output when sql_trace is False"""
        # Ensure SQL trace is disabled
        model.sql_trace = False

        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            # Execute a query
            Person = model.get_relation_class(PERSON)
            person = Person()
            list(person.ho_select(limit=1))

            # Get the output
            output = captured_output.getvalue()

            # Verify that trace information is NOT present
            self.assertNotIn('SQL TRACE', output)
            self.assertNotIn('File:', output)

        finally:
            # Restore stdout
            sys.stdout = sys.__stdout__

    def test_sql_trace_shows_correct_caller_location(self):
        """Test that SQL trace shows the correct caller location"""
        # Enable SQL trace
        model.sql_trace = True

        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            # Execute a query from a specific location
            Person = model.get_relation_class(PERSON)
            person = Person()
            result = list(person.ho_select(limit=1))  # This line should be traced

            # Get the output
            output = captured_output.getvalue()

            # Verify that the traced line contains 'ho_select'
            self.assertIn('ho_select', output)

            # Verify that it shows this test file
            self.assertIn('sql_trace_test.py', output)

        finally:
            # Restore stdout
            sys.stdout = sys.__stdout__
            model.sql_trace = False

    def test_sql_trace_with_count(self):
        """Test SQL trace with ho_count method"""
        model.sql_trace = True

        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            Person = model.get_relation_class(PERSON)
            person = Person()
            count = person.ho_count()

            output = captured_output.getvalue()

            # Verify trace is present
            self.assertIn('SQL TRACE', output)
            # Verify count query is present
            self.assertIn('count', output.lower())

        finally:
            sys.stdout = sys.__stdout__
            model.sql_trace = False

    def test_sql_trace_with_update(self):
        """Test SQL trace with ho_update method"""
        model.sql_trace = True

        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            Person = model.get_relation_class(PERSON)
            # Create a specific person to update
            person = Person(first_name='TestFirstName', last_name='TestLastName')

            # Try to update (may fail if person doesn't exist, but we just want to test trace)
            try:
                person.ho_update(first_name='NewName')
            except Exception:
                pass  # We don't care if update fails, just testing trace

            output = captured_output.getvalue()

            # Verify trace is present
            self.assertIn('SQL TRACE', output)

        finally:
            sys.stdout = sys.__stdout__
            model.sql_trace = False

    def test_get_caller_info_with_invalid_skip_frames(self):
        """Test get_caller_info returns None when skip_frames is too large"""
        # Call with a very large skip_frames value
        caller_info = utils.get_caller_info(skip_frames=100)
        self.assertIsNone(caller_info)

    def test_sql_trace_caller_info_format(self):
        """Test that caller info is properly formatted"""
        model.sql_trace = True

        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            Person = model.get_relation_class(PERSON)
            person = Person()
            list(person.ho_select(limit=1))

            output = captured_output.getvalue()

            # Split output into lines and check format
            lines = [line.strip() for line in output.split('\n') if line.strip()]

            # Find the SQL TRACE section
            trace_found = False
            for i, line in enumerate(lines):
                if 'SQL TRACE' in line:
                    trace_found = True
                    # Check that following lines have expected format
                    self.assertTrue(any('File:' in l for l in lines[i:i+5]))
                    self.assertTrue(any('Function:' in l for l in lines[i:i+5]))
                    self.assertTrue(any('Code:' in l for l in lines[i:i+5]))
                    break

            self.assertTrue(trace_found, "SQL TRACE section not found in output")

        finally:
            sys.stdout = sys.__stdout__
            model.sql_trace = False
