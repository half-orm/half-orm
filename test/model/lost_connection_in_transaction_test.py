#!/usr/bin/env python3
# -*- coding:  utf-8 -*-

"""A connection lost inside a transaction must surface as an error. The
failed query used to be replayed on a fresh connection, in autocommit mode:
committed on its own, outside the transaction it belonged to."""

import psycopg
import pytest

from half_orm.transaction import Transaction
from ..init import model

MARKER = 'lost connection in transaction'


def _person(first_name):
    return model.get_relation_class('actor.person')(
        last_name=MARKER, first_name=first_name, birth_date='2000-01-01')


def _kill_backend_of(a_model):
    pid = a_model._connection.info.backend_pid
    params = {key: value for key, value in a_model._dbinfo.items() if value is not None}
    with psycopg.connect(**params, autocommit=True) as other:
        other.execute('select pg_terminate_backend(%s)', (pid,))


@pytest.fixture(autouse=True)
def cleanup():
    yield
    model.get_relation_class('actor.person')(last_name=MARKER).ho_delete()


def test_query_is_not_replayed_outside_the_transaction():
    with pytest.raises((psycopg.OperationalError, psycopg.InterfaceError)):
        with Transaction(model):
            _person('before').ho_insert()
            _kill_backend_of(model)
            _person('after').ho_insert()
    # Neither row: the first went with the connection, and the second must
    # not have been committed on its own by a retry.
    assert model.get_relation_class('actor.person')(last_name=MARKER).ho_count() == 0


def test_model_is_usable_afterwards():
    with pytest.raises((psycopg.OperationalError, psycopg.InterfaceError)):
        with Transaction(model):
            _kill_backend_of(model)
            _person('after').ho_insert()
    assert model._connection.autocommit
    _person('later').ho_insert()
    assert model.get_relation_class('actor.person')(last_name=MARKER).ho_count() == 1


def test_outside_a_transaction_the_query_is_still_retried():
    _kill_backend_of(model)
    _person('retried').ho_insert()
    assert model.get_relation_class('actor.person')(last_name=MARKER).ho_count() == 1
