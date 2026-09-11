#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for Model._import_class.

The module path is built from the relation's schema and name, which are
database data, and importing a module runs it.
"""

import sys
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from half_orm.model import Model, _module_is_absent

from ..init import model


class TestModuleIsAbsent(TestCase):
    """Telling "no such module" from "that module is broken".

    Both raise ModuleNotFoundError; only `exc.name` separates them.
    """

    def test_the_module_itself_is_missing(self):
        exc = ModuleNotFoundError(name='scope.blog.post')
        self.assertTrue(_module_is_absent(exc, 'scope.blog.post'))

    def test_a_parent_package_is_missing(self):
        exc = ModuleNotFoundError(name='scope.blog')
        self.assertTrue(_module_is_absent(exc, 'scope.blog.post'))

    def test_something_the_module_imports_is_missing(self):
        """The relation's module exists; its own import is what failed."""
        exc = ModuleNotFoundError(name='scope.blog.helpers')
        self.assertFalse(_module_is_absent(exc, 'scope.blog.post'))

    def test_an_unrelated_module_is_missing(self):
        exc = ModuleNotFoundError(name='requests')
        self.assertFalse(_module_is_absent(exc, 'scope.blog.post'))

    def test_a_nameless_error(self):
        self.assertFalse(_module_is_absent(ImportError('boom'), 'scope.blog.post'))


class TestImportClassScope(TestCase):
    """A scope package is what roots the module path."""

    def setUp(self):
        self.model = Model('halftest')

    def test_no_scope_imports_nothing(self):
        """Without a scope, the path would be a top-level module named by
        whoever can create a schema in the database."""
        self.model._scope = None
        before = set(sys.modules)
        cls = self.model._import_class('"blog"."post"')
        self.assertIs(cls, self.model.get_relation_class('"blog"."post"'))
        self.assertFalse({m for m in set(sys.modules) - before
                          if m.startswith('blog')})

    def test_a_name_that_cannot_be_a_module_is_not_looked_up(self):
        self.model._scope = 'anything'
        before = set(sys.modules)
        with self.assertRaises(Exception):
            # No such relation either; the point is that nothing was imported.
            self.model._import_class('"a-b"."c"')
        self.assertFalse({m for m in set(sys.modules) - before
                          if m.startswith('anything')})


class TestImportClassFromScope(TestCase):
    """Loading the caller's own class, and failing to."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.scope = 'tmpscope_for_tests'
        package = self.tmp / self.scope / 'blog'
        package.mkdir(parents=True)
        (self.tmp / self.scope / '__init__.py').write_text('')
        (package / '__init__.py').write_text('')
        self.module = package / 'post.py'
        sys.path.insert(0, str(self.tmp))
        self.model = Model('halftest')

    def tearDown(self):
        sys.path.remove(str(self.tmp))
        for name in [m for m in sys.modules if m.startswith(self.scope)]:
            del sys.modules[name]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _import(self):
        return self.model._import_class('"blog"."post"', scope=self.scope)

    def test_the_class_is_taken_from_the_module(self):
        self.module.write_text('class Post:\n    marker = "mine"\n')
        self.assertEqual(self._import().marker, 'mine')

    def test_no_module_falls_back_quietly(self):
        """Most relations have no module of their own; that is not an error."""
        self.assertIs(
            self._import(), self.model.get_relation_class('"blog"."post"'))

    def test_a_module_without_the_class_falls_back(self):
        self.module.write_text('OTHER = 1\n')
        self.assertIs(
            self._import(), self.model.get_relation_class('"blog"."post"'))

    def test_a_broken_import_is_reported(self):
        """A bare `except:` used to delete the caller's code from the program
        without a word: the generated class arrived without their methods."""
        self.module.write_text('from .helpers import thing\n\nclass Post:\n    pass\n')
        with self.assertRaises(ModuleNotFoundError) as ctx:
            self._import()
        self.assertIn('helpers', str(ctx.exception))

    def test_an_error_raised_by_the_module_is_reported(self):
        self.module.write_text('raise RuntimeError("boom")\n\nclass Post:\n    pass\n')
        with self.assertRaises(RuntimeError):
            self._import()

    def test_a_syntax_error_is_reported(self):
        self.module.write_text('class Post(\n')
        with self.assertRaises(SyntaxError):
            self._import()
