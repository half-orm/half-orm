#!/usr/bin/env python3
# -*- coding:  utf-8 -*-

"""A dot may belong to a schema name or to a relation name. Several places
took a `schema.relation` string apart on its last dot, which is only right
when the relation's own name holds none."""

import os

import pytest

from half_orm.model import Model, register, CONF_DIR
from half_orm.model_errors import UnknownRelation
from ..init import model

CONF = 'halftest_dotted_names'

SETUP = '''
create schema hodot;
create schema "hodot.s";
create table "hodot.s".t (id int primary key);
create table hodot."b.c" (id int primary key, label text);
create table hodot.ref (id int primary key, bc_id int references hodot."b.c"(id));
create table hodot."p.q" (id int primary key);
create table hodot.child () inherits (hodot."p.q");
'''
TEARDOWN = 'drop schema if exists hodot cascade; drop schema if exists "hodot.s" cascade;'


@pytest.fixture(scope='module')
def dot_model():
    conf = os.path.join(CONF_DIR, CONF)
    model.execute_query(TEARDOWN)
    model.execute_query(SETUP)
    try:
        # Another host name, hence a Model of its own: its catalog is read
        # now, without reloading the one the other test modules share.
        with open(conf, 'w', encoding='utf-8') as file_:
            file_.write(
                '[database]\nname = halftest\nuser = halftest\n'
                'password = halftest\nhost = 127.0.0.1\n')
        a_model = Model(CONF)
        # Another test module may already have read the catalog through this
        # host name, before the schema existed.
        a_model.reconnect(reload=True)
        yield a_model
        a_model.disconnect()
    finally:
        if os.path.exists(conf):
            os.remove(conf)
        model.execute_query(TEARDOWN)


@pytest.mark.parametrize('name, fqrn', [
    ('hodot.b.c', ('hodot', 'b.c')),          # unquoted: the catalog decides
    ('hodot."b.c"', ('hodot', 'b.c')),
    ('"hodot"."b.c"', ('hodot', 'b.c')),
    ('hodot.s.t', ('hodot.s', 't')),
    ('"hodot.s".t', ('hodot.s', 't')),
    ('hodot.ref', ('hodot', 'ref')),
])
def test_get_relation_class_finds_the_relation(dot_model, name, fqrn):
    assert dot_model.get_relation_class(name)._t_fqrn[1:] == fqrn


@pytest.mark.parametrize('name, expected', [
    ('hodot.b.c', True),
    ('hodot."b.c"', True),
    ('hodot.s.t', True),
    ('hodot.ref', True),
    ('hodot.nope', False),
    ('hodot.b.nope', False),
    ('no_schema', False),
])
def test_has_relation(dot_model, name, expected):
    assert dot_model.has_relation(name) is expected


def test_unknown_dotted_name_is_still_split_on_its_last_dot(dot_model):
    with pytest.raises(UnknownRelation) as exc:
        dot_model.get_relation_class('hodot.s.nope')
    assert (exc.value.schema, exc.value.relation) == ('hodot.s', 'nope')


def test_register_uses_the_key_of_its_own_relation(dot_model):
    @register
    class BC(dot_model.get_relation_class('hodot."b.c"')):
        pass
    key = (dot_model._dbname, 'hodot', 'b.c')
    try:
        assert dot_model._classes_[dot_model._dbname][key] is BC
        assert dot_model.get_relation_class('hodot."b.c"') is BC
        assert (dot_model._dbname, 'hodot.b', 'c') not in dot_model._classes_[dot_model._dbname]
    finally:
        BC._rels_ids.pop(id(BC), None)


def test_inheritance_from_a_dotted_parent(dot_model):
    child = dot_model.get_relation_class('hodot.child')
    parent = dot_model.get_relation_class('hodot."p.q"')
    assert parent._t_fqrn in {cls._t_fqrn for cls in child.__mro__ if hasattr(cls, '_t_fqrn')}
    assert child().ho_count() == 0


def test_read_set_through_a_foreign_key_to_a_dotted_relation(dot_model):
    ref = dot_model.get_relation_class('hodot.ref')()
    fkey = next(fk for name, fk in ref._ho_fkeys.items() if not name.startswith('_reverse'))
    fkey.set(label='x')
    assert ref.ho_read_set() == frozenset({'hodot.ref', 'hodot.b.c'})
