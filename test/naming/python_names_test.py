#!/usr/bin/env python3
# -*- coding:  utf-8 -*-

"""A column is known to Python by one name, everywhere.

A column whose name Python cannot write (`"a = 1"`, exposed as `column2`) or
that was given another one (`title`, declared `heading`) is reached through
that Python name. Everything that takes a column name accepts it, and every
row comes back keyed by it -- whatever the form of the call, so that a row
can be handed back to a constructor.

These tests describe that contract. Some of them fail on the code as it
stands: those are the bugs to fix.
"""

import asyncio
import io
import os

import pytest

from half_orm.model import Model, CONF_DIR
from half_orm.relation_errors import UnknownAttributeError
from ..init import model

CONF = 'halftest_python_names'

SETUP = '''
create schema hopy;
create table hopy.parent (id int primary key, label text);
create table hopy.t (
    id int primary key,
    "a = 1" int,
    title text,
    parent_id int references hopy.parent(id)
);
insert into hopy.parent values (1, 'p'), (2, 'q');
insert into hopy.t values (1, 30, 'x', 1), (2, 10, 'y', 1), (3, 20, 'z', 2);
'''
TEARDOWN = 'drop schema if exists hopy cascade'

ODD = 'column2'          # "a = 1", which Python cannot write
RENAMED = 'heading'      # title, renamed on the Model
PY_NAMES = {'id', ODD, RENAMED, 'parent_id'}


@pytest.fixture(scope='module')
def py_model():
    conf = os.path.join(CONF_DIR, CONF)
    model.execute_query(TEARDOWN)
    model.execute_query(SETUP)
    with open(conf, 'w', encoding='utf-8') as file_:
        file_.write(
            '[database]\nname = halftest\nuser = halftest\n'
            'password = halftest\nhost = 127.0.0.1\n')
    try:
        a_model = Model(CONF, field_names={'hopy.t': {'title': RENAMED}})
        a_model.reconnect(reload=True)
        yield a_model
        a_model.disconnect()
    finally:
        os.remove(conf)
        model.execute_query(TEARDOWN)


@pytest.fixture
def T(py_model):
    return py_model.get_relation_class('hopy.t')


@pytest.fixture
def P(py_model):
    return py_model.get_relation_class('hopy.parent')


@pytest.fixture
def cleanup(T):
    yield
    T(id=('>=', 100)).ho_delete()


def _fkey(rel, prefix):
    return getattr(rel, next(a for a in rel._ho_fkeys_attr if a.startswith(prefix)))


def test_fixture_names(T):
    "the premise of every other test"
    assert set(T()._ho_fields) == PY_NAMES
    assert T()._ho_fields[ODD].name == 'a = 1'
    assert T()._ho_fields[RENAMED].name == 'title'


# -- every row is keyed by Python names ----------------------------------------

def test_ho_select_without_arguments(T):
    assert set(next(T(id=1).ho_select())) == PY_NAMES


def test_ho_select_with_arguments(T):
    assert next(T(id=1).ho_select(ODD, RENAMED)) == {ODD: 30, RENAMED: 'x'}


def test_ho_select_distinct(T):
    assert set(next(T(id=1).ho_select(distinct=True))) == PY_NAMES


def test_iterating_a_relation(T):
    assert set(next(iter(T(id=1)))) == PY_NAMES


def test_ho_get_without_arguments(T):
    assert T(id=1).ho_get() == {'id': 1, ODD: 30, RENAMED: 'x', 'parent_id': 1}


def test_ho_insert_returns_python_names(T, cleanup):
    row = T(id=100, **{ODD: 1, RENAMED: 'i'}).ho_insert()
    assert row == {'id': 100, ODD: 1, RENAMED: 'i', 'parent_id': None}


def test_ho_insert_star_returns_python_names(T, cleanup):
    assert set(T(id=101).ho_insert('*')) == PY_NAMES


def test_upsert_returns_python_names(T, cleanup):
    T(id=102, **{ODD: 1}).ho_insert()
    assert set(T(id=102, **{ODD: 2}).ho_insert(upsert=True)) == PY_NAMES


def test_ho_update_star_returns_python_names(T, cleanup):
    T(id=103).ho_insert()
    assert [set(row) for row in T(id=103).ho_update('*', **{ODD: 5})] == [PY_NAMES]


def test_ho_delete_star_returns_python_names(T):
    T(id=104).ho_insert()
    assert [set(row) for row in T(id=104).ho_delete('*')] == [PY_NAMES]


def test_union_through_foreign_keys(T):
    "| with joins on either side is rendered as a UNION of SELECT r.*"
    left = T(id=1)
    _fkey(left, 'fk_').set()
    rows = list((left | T(id=3)).ho_select())
    assert sorted(row['id'] for row in rows) == [1, 3]
    assert all(set(row) == PY_NAMES for row in rows)


def test_a_row_goes_back_into_a_constructor(T):
    "the round trip the json_agg tests rely on"
    assert T(**T(id=1).ho_get()).ho_count() == 1


def test_async_rows_use_python_names(py_model, T):
    async def run():
        await py_model.aconnect()
        try:
            rows = await T(id=1).ho_aselect()
            row = await T(id=1).ho_aget()
            return rows, row
        finally:
            await py_model.adisconnect()
    rows, row = asyncio.run(run())
    assert [set(r) for r in rows] == [PY_NAMES]
    assert set(row) == PY_NAMES


# -- every column name an argument carries is a Python name ---------------------

@pytest.mark.parametrize('order_by, expected', [
    (ODD, [2, 3, 1]),                 # "a = 1": 10, 20, 30
    (f'{ODD} desc', [1, 3, 2]),
    (RENAMED, [1, 2, 3]),             # title: x, y, z
    (f'{RENAMED} desc, id', [3, 2, 1]),
])
def test_order_by(T, order_by, expected):
    assert [row['id'] for row in T().ho_select('id', order_by=order_by)] == expected


def test_order_by_refuses_the_sql_name(T):
    with pytest.raises(UnknownAttributeError):
        list(T().ho_select('id', order_by='"a = 1"'))
    with pytest.raises(UnknownAttributeError):
        list(T().ho_select('id', order_by='title'))


def test_ho_copy_from_dicts(T, cleanup):
    assert T.ho_copy([{'id': 110, ODD: 7, RENAMED: 'c'}]) == 1
    assert T(id=110).ho_get(ODD, RENAMED) == {ODD: 7, RENAMED: 'c'}


def test_ho_copy_from_csv(T, cleanup):
    data = io.StringIO(f'id,{ODD},{RENAMED}\n111,8,d\n')
    assert T.ho_copy(data) == 1
    assert T(id=111).ho_get(ODD, RENAMED) == {ODD: 8, RENAMED: 'd'}


def test_ho_copy_from_csv_with_explicit_columns(T, cleanup):
    data = io.StringIO('112,9,e\n')
    assert T.ho_copy(data, columns=['id', ODD, RENAMED]) == 1
    assert T(id=112).ho_get(ODD, RENAMED) == {ODD: 9, RENAMED: 'e'}


def test_ho_copy_refuses_the_sql_name(T):
    with pytest.raises(UnknownAttributeError):
        T.ho_copy([{'id': 113, 'a = 1': 1}])


@pytest.mark.parametrize('distinct', [False, True])
def test_json_agg_fields(P, distinct):
    parent = P(id=1)
    rfk = _fkey(parent, 'rfk_')
    rfk.set()
    attr = next(a for a in parent._ho_fkeys_attr if a.startswith('rfk_'))
    spec = {'fields': [ODD, RENAMED], 'distinct': distinct}
    row = next(parent.ho_select('id', json_agg={attr: spec}))
    assert sorted(row[attr], key=lambda o: o[ODD]) == [
        {ODD: 10, RENAMED: 'y'}, {ODD: 30, RENAMED: 'x'}]


@pytest.mark.parametrize('distinct', [False, True])
def test_json_agg_whole_rows(P, distinct):
    "with no field list the whole row is aggregated -- keyed by Python names too"
    parent = P(id=2)
    _fkey(parent, 'rfk_').set()
    attr = next(a for a in parent._ho_fkeys_attr if a.startswith('rfk_'))
    row = next(parent.ho_select('id', json_agg={attr: {'fields': [], 'distinct': distinct}}))
    assert [set(o) for o in row[attr]] == [PY_NAMES]


def test_json_agg_scalar_field(P):
    parent = P(id=1)
    _fkey(parent, 'rfk_').set()
    attr = next(a for a in parent._ho_fkeys_attr if a.startswith('rfk_'))
    row = next(parent.ho_select('id', json_agg={attr: ODD}))
    assert sorted(row[attr]) == [10, 30]


# -- foreign keys whose columns are known under another name --------------------
#
# A foreign key names its columns as the database does. The paths below used
# to look those names up among the Python ones.

FK_CONF = 'halftest_python_names_fk'
FK_SETUP = '''
create schema hopyfk;
create table hopyfk.parent (id int primary key, label text);
create table hopyfk.child (id int primary key, parent_id int references hopyfk.parent(id));
insert into hopyfk.parent values (1, 'p'), (2, 'q');
insert into hopyfk.child values (10, 1), (11, 1), (12, 2);
'''
FK_TEARDOWN = 'drop schema if exists hopyfk cascade'


@pytest.fixture(scope='module')
def fk_model():
    conf = os.path.join(CONF_DIR, FK_CONF)
    model.execute_query(FK_TEARDOWN)
    model.execute_query(FK_SETUP)
    with open(conf, 'w', encoding='utf-8') as file_:
        file_.write(
            '[database]\nname = halftest\nuser = halftest\n'
            'password = halftest\nhost = 127.0.0.1\n')
    try:
        a_model = Model(FK_CONF, field_names={
            'hopyfk.parent': {'id': 'pid'},
            'hopyfk.child': {'parent_id': 'parent'}})
        a_model.reconnect(reload=True)
        yield a_model
        a_model.disconnect()
    finally:
        os.remove(conf)
        model.execute_query(FK_TEARDOWN)


@pytest.fixture
def child(fk_model):
    return fk_model.get_relation_class('hopyfk.child')


@pytest.fixture
def parent(fk_model):
    return fk_model.get_relation_class('hopyfk.parent')


def test_fk_navigation_both_ways(child, parent):
    assert [r['pid'] for r in _fkey(child(id=10), 'fk_')().ho_select()] == [1]
    assert sorted(r['id'] for r in _fkey(parent(pid=1), 'rfk_')().ho_select()) == [10, 11]


def test_fk_values(child, parent):
    fkey = _fkey(child(), 'fk_')
    fkey.set(parent(pid=2))
    assert fkey.values() == [[2]]


def test_insert_with_a_foreign_key_set(child, parent):
    rel = child(id=20)
    _fkey(rel, 'fk_').set(parent(pid=2))
    try:
        assert rel.ho_insert() == {'id': 20, 'parent': 2}
    finally:
        child(id=20).ho_delete()


def test_singleton_through_a_foreign_key(child, parent):
    """Fixing the foreign-key column of the child, under its Python name,
    identifies one parent -- as Comment(post_id=42).fk_post() does."""
    assert _fkey(child(parent=1), 'fk_')().ho_assert_is_singleton() is not None


def test_not_a_singleton_when_the_foreign_key_column_is_free(child, parent):
    from half_orm.relation_errors import NotASingletonError
    with pytest.raises(NotASingletonError):
        _fkey(child(id=10), 'fk_')().ho_assert_is_singleton()
