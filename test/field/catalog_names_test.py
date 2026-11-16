#!/usr/bin/env python3
# -*- coding:  utf-8 -*-

"""Names read from the catalog are interpolated into statements. PostgreSQL
lets a column or a type be called anything, so they must be quoted for what
they are: a quote inside a column name, or a type named after a statement,
used to reach the query as SQL."""

import os

import pytest
from psycopg import ClientCursor

from half_orm.model import Model, CONF_DIR
from half_orm.null import NULL
from ..init import model

SCHEMA = 'ho_catalog_names'
CONF = 'halftest_catalog_names'
EVIL_TYPE = 'int4); select pg_sleep(0); --'

SETUP = f'''
create schema {SCHEMA};
create type {SCHEMA}."{EVIL_TYPE}" as enum ('x', 'y');
create table {SCHEMA}.odd (
    id int primary key,
    "a""b" text,
    v {SCHEMA}."{EVIL_TYPE}",
    flag boolean
);
insert into {SCHEMA}.odd values (1, 'one', 'x', true), (2, 'two', 'y', null), (3, 'three', 'x', false);
create table {SCHEMA}.parent ("PId" int primary key, label text);
create table {SCHEMA}.child (id int primary key, "ParentRef" int references {SCHEMA}.parent("PId"));
insert into {SCHEMA}.parent values (10, 'ten'), (20, 'twenty');
insert into {SCHEMA}.child values (1, 10), (2, 10), (3, 20);
'''


@pytest.fixture(scope='module')
def names_model():
    conf = os.path.join(CONF_DIR, CONF)
    model.execute_query(f'drop schema if exists {SCHEMA} cascade')
    model.execute_query(SETUP)
    try:
        # Reached through another host name: a Model of its own, whose
        # catalog is read now that the schema exists, without reloading the
        # one every other test module shares.
        with open(conf, 'w', encoding='utf-8') as file_:
            file_.write(
                '[database]\nname = halftest\nuser = halftest\n'
                'password = halftest\nhost = 127.0.0.1\n')
        a_model = Model(CONF)
        # the type lives in a schema that is not on the default search_path
        a_model.execute_query(f'set search_path to public, {SCHEMA}')
        yield a_model
        a_model.disconnect()
    finally:
        if os.path.exists(conf):
            os.remove(conf)
        model.execute_query(f'drop schema if exists {SCHEMA} cascade')


def _field(rel, column):
    "The Field of `rel` whose column is named `column`, whatever its Python name."
    return next(f for f in rel._ho_fields.values() if f.name == column)


def _py_name(rel, column):
    return next(k for k, f in rel._ho_fields.items() if f.name == column)


def test_quote_in_column_name_where(names_model):
    odd = names_model.get_relation_class(f'{SCHEMA}.odd')()
    _field(odd, 'a"b').set('two')
    query, _ = odd._ho_prep_select()
    assert '."a""b" = ' in query
    assert [row['id'] for row in odd.ho_select('id')] == [2]


def test_quote_in_column_name_insert_update_upsert(names_model):
    Odd = names_model.get_relation_class(f'{SCHEMA}.odd')
    py_name = _py_name(Odd(), 'a"b')
    try:
        Odd(**{'id': 100, py_name: 'new'}).ho_insert()
        Odd(id=100).ho_update(**{py_name: 'updated'})
        assert _one(Odd(id=100), py_name) == 'updated'
        Odd(**{'id': 100, py_name: 'upserted'}).ho_insert(upsert=True)
        assert _one(Odd(id=100), py_name) == 'upserted'
    finally:
        Odd(id=100).ho_delete()


def _one(rel, py_name):
    return rel.ho_get(py_name)[py_name]


def test_type_name_is_quoted_in_cast(names_model):
    odd = names_model.get_relation_class(f'{SCHEMA}.odd')()
    odd.v.set('x')
    query, _ = odd._ho_prep_select()
    assert f'%s::"{EVIL_TYPE}"' in query
    assert sorted(row['id'] for row in odd.ho_select('id')) == [1, 3]


def test_builtin_type_cast_is_left_bare(names_model):
    odd = names_model.get_relation_class(f'{SCHEMA}.odd')(id=1)
    query, _ = odd._ho_prep_select()
    assert '%s::int4' in query


def test_join_quotes_the_referenced_column(names_model):
    Child = names_model.get_relation_class(f'{SCHEMA}.child')
    Parent = names_model.get_relation_class(f'{SCHEMA}.parent')
    child = Child()
    fkey = next(fk for name, fk in child._ho_fkeys.items()
                if not name.startswith('_reverse'))
    fkey.set(Parent(label='ten'))
    query, _ = child._ho_prep_select()
    assert '."PId" = ' in query and '."ParentRef"' in query
    assert child.ho_count() == 2


@pytest.mark.parametrize('comp, value, expected', [
    ('is', True, [1]),
    ('is', False, [3]),
    ('is not', True, [2, 3]),
    ('is not', False, [1, 2]),
    ('is', NULL, [2]),
    ('is not', NULL, [1, 3]),
])
def test_is_takes_true_false_and_null(names_model, comp, value, expected):
    odd = names_model.get_relation_class(f'{SCHEMA}.odd')()
    odd.flag.set((comp, value))
    assert sorted(row['id'] for row in odd.ho_select('id')) == expected


@pytest.mark.parametrize('value', [1, 'true', 0])
def test_is_refuses_anything_else(names_model, value):
    odd = names_model.get_relation_class(f'{SCHEMA}.odd')()
    with pytest.raises(ValueError):
        odd.flag.set(('is', value))


@pytest.mark.parametrize('comp', ['%', '%>', '<%', '<<%'])
def test_percent_in_an_operator_is_escaped(names_model, comp):
    odd = names_model.get_relation_class(f'{SCHEMA}.odd')()
    _field(odd, 'a"b').set((comp, 'x'))
    query, values = odd._ho_prep_select()
    rendered = ClientCursor(names_model._connection).mogrify(
        query, names_model._unwrap_values(values))
    assert f' {comp} ' in rendered
