#-*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods, protected-access

"""This module provides the Transaction class."""

import sys
import threading

import psycopg

class Transaction:
    """Context manager for atomic database operations.

    Wraps one or more SQL operations in a single transaction: commits on
    success, rolls back on exception. Transactions are per-thread and
    per-model instance.

    Nested ``with Transaction(model)`` blocks use PostgreSQL savepoints
    automatically: an exception in an inner block rolls back only that inner
    block, leaving the outer transaction intact.

    Args:
        model (Model): the :class:`~half_orm.model.Model` instance whose
            connection should be used.

    Example:
        Atomic insert of two related rows::

            from half_orm.transaction import Transaction

            with Transaction(blog):
                alice = Author(
                    first_name='Alice', last_name='Martin',
                    email='alice@example.com',
                ).ho_insert()
                Post(
                    title='First post', content='Hello world',
                    author_id=alice['id'],
                ).ho_insert()
            # both rows are committed, or neither is

        Nested transactions use savepoints::

            with Transaction(blog):
                alice = Author(...).ho_insert()
                with Transaction(blog):          # savepoint
                    Post(...).ho_insert()
                    # exception here rolls back only the post, not Alice
    """

    __tls = threading.local()

    def __call__(self, model):
        if not hasattr(self.__class__.__tls, 'transactions'):
            self.__class__.__tls.transactions = {}
        transactions = self.__class__.__tls.transactions
        self.__id = id(model)
        self.__transaction = None
        if self.__id not in transactions:
            transactions[self.__id] = {
                'level': 0, 'model': model,
                'sp_counter': 0, 'sp_stack': [],
            }
        self.__transaction = transactions[self.__id]

    __init__ = __call__

    def __enter__(self):
        conn = self.__transaction['model']._connection
        if conn.autocommit:
            conn.autocommit = False
        if self.__transaction['level'] > 0:
            self.__transaction['sp_counter'] += 1
            sp_name = f'sp_{self.__transaction["sp_counter"]}'
            self.__transaction['sp_stack'].append(sp_name)
            with conn.cursor() as cur:
                cur.execute(f'SAVEPOINT {sp_name}')
        self.__transaction['level'] += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__transaction['level'] -= 1
        conn = self.__transaction['model']._connection
        if self.__transaction['level'] > 0:
            sp_name = self.__transaction['sp_stack'].pop()
            with conn.cursor() as cur:
                if exc_type is not None:
                    cur.execute(f'ROLLBACK TO SAVEPOINT {sp_name}')
                cur.execute(f'RELEASE SAVEPOINT {sp_name}')
        else:
            try:
                conn.commit()
                conn.autocommit = True
            except psycopg.Error:
                conn.rollback()
        return False

    @property
    def level(self):
        return self.__transaction.get('level')

    def is_set(self):
        return self.__transaction.get('level', 0) > 0
