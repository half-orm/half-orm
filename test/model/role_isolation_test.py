#!/usr/bin/env python3
# -*- coding:  utf-8 -*-

"""Two Models on one database under different roles must not answer for
one another: relation classes used to be shared by database name alone, so
the second Model ran its queries through the first one's connection."""

import os

import psycopg
import pytest

from half_orm.model import Model, register, CONF_DIR
from ..init import model

RO_ROLE = 'halftest_ro_isolation'
RO_CONF = 'halftest_ro_isolation'
PERSON = 'actor.person'


def _current_user(a_model):
    return a_model.execute_query('select current_user').fetchone()['current_user']


@pytest.fixture(scope='module')
def ro_model():
    conf = os.path.join(CONF_DIR, RO_CONF)
    # No skip on a refusal: the test role is a superuser, as the CI workflows
    # set it up, and a suite that quietly drops these tests proves nothing.
    model.execute_query(f"create role {RO_ROLE} login password '{RO_ROLE}'")
    try:
        model.execute_query(f'grant usage on schema actor to {RO_ROLE}')
        model.execute_query(f'grant select on actor.person to {RO_ROLE}')
        with open(conf, 'w', encoding='utf-8') as file_:
            file_.write(
                f'[database]\nname = halftest\nuser = {RO_ROLE}\n'
                f'password = {RO_ROLE}\nhost = localhost\n')
        ro = Model(RO_CONF)
        yield ro
        ro.disconnect()
    finally:
        if os.path.exists(conf):
            os.remove(conf)
        # Revoked one by one: DROP OWNED BY needs the privileges of the role
        # itself, which creating it does not confer since PostgreSQL 16.
        model.execute_query(f'revoke all on actor.person from {RO_ROLE}')
        model.execute_query(f'revoke all on schema actor from {RO_ROLE}')
        model.execute_query(f'drop role {RO_ROLE}')


def test_models_keep_their_own_role(ro_model):
    assert _current_user(ro_model) == RO_ROLE
    assert _current_user(model) != RO_ROLE


def test_class_is_bound_to_the_model_that_generated_it(ro_model):
    assert ro_model.get_relation_class(PERSON)._ho_model is ro_model
    assert model.get_relation_class(PERSON)._ho_model is model


def test_read_only_model_cannot_write(ro_model):
    person = ro_model.get_relation_class(PERSON)
    assert person().ho_count() >= 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        person(last_name='role isolation').ho_update(first_name='nope')


def test_registered_class_does_not_cross_roles(ro_model):
    @register
    class Person(model.get_relation_class(PERSON)):
        pass
    try:
        key = (model._dbname, 'actor', 'person')
        assert model._classes_[model._dbname][key] is Person
        assert ro_model.get_relation_class(PERSON) is not Person
        assert ro_model._classes_.get(ro_model._dbname, {}).get(key) is not Person
    finally:
        # Leave the shared registry as the other test modules expect it.
        del model._classes_[model._dbname][key]
        Person._rels_ids.pop(id(Person), None)


def test_same_role_models_still_share_classes():
    other = Model('halftest')
    assert other.get_relation_class(PERSON) is model.get_relation_class(PERSON)
