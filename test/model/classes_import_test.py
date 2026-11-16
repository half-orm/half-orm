#!/usr/bin/env python3
# -*- coding:  utf-8 -*-

"""Model.classes() builds a module path out of schema and relation names,
which are database content, and imports it."""

from unittest import mock

import pytest

from ..init import model

SENTINEL = object()


def _classes_with(relations, import_module):
    with mock.patch.object(model, '_relations', return_value=relations), \
         mock.patch.object(model, 'get_relation_class', return_value=SENTINEL), \
         mock.patch('half_orm.model.importlib.import_module', import_module):
        return list(model.classes())


@pytest.mark.parametrize('schema', ['..actor', 'my-schema', 'a b', '1abc', ''])
def test_a_name_that_is_not_importable_is_not_handed_to_import(schema):
    import_module = mock.Mock()
    result = _classes_with([('r', ('halftest', schema, 'person'))], import_module)
    import_module.assert_not_called()
    assert result == [(SENTINEL, 'r')]


def test_missing_module_falls_back_to_the_generated_class():
    import_module = mock.Mock(
        side_effect=ModuleNotFoundError(name='halftest.actor.person'))
    result = _classes_with([('r', ('halftest', 'actor', 'person'))], import_module)
    assert result == [(SENTINEL, 'r')]


def test_missing_package_falls_back_to_the_generated_class():
    import_module = mock.Mock(side_effect=ModuleNotFoundError(name='halftest'))
    result = _classes_with([('r', ('halftest', 'actor', 'person'))], import_module)
    assert result == [(SENTINEL, 'r')]


def test_a_module_whose_own_import_fails_is_reported():
    import_module = mock.Mock(
        side_effect=ModuleNotFoundError(name='a_dependency_that_is_missing'))
    with pytest.raises(ModuleNotFoundError):
        _classes_with([('r', ('halftest', 'actor', 'person'))], import_module)
