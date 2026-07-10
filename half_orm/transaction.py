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
        Atomic insert of two related rows:
            ```python
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
            ```

        Nested transactions use savepoints:
            ```python
            with Transaction(blog):
                alice = Author(...).ho_insert()
                with Transaction(blog):          # savepoint
                    Post(...).ho_insert()
                    # exception here rolls back only the post, not Alice
            ```

    *New in version 0.18.0:* nested ``Transaction`` blocks use savepoints.
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


class AsyncTransaction:
    """Async context manager for atomic database operations.

    Async counterpart of :class:`Transaction`: drives the model's async
    connection (``model._aconnection``, set up via ``await
    model.aconnect()``) instead of the sync one. Wraps one or more
    ``ho_a*`` operations in a single transaction: commits on success, rolls
    back on exception. Transactions are tracked per-model-instance (keyed
    by ``id(model)``) — unlike :class:`Transaction`, there is no per-thread
    isolation, since asyncio concurrency is task-based rather than
    thread-based and a model's async connection is only ever driven from
    one place at a time regardless of which thread runs the event loop.

    Nested ``async with AsyncTransaction(model)`` blocks use PostgreSQL
    savepoints automatically: an exception in an inner block rolls back
    only that inner block, leaving the outer transaction intact.

    Args:
        model (Model): the :class:`~half_orm.model.Model` instance whose
            async connection should be used.

    Example:
        Atomic insert of two related rows:
            ```python
            from half_orm.transaction import AsyncTransaction

            async with AsyncTransaction(blog):
                alice = await Author(
                    first_name='Alice', last_name='Martin',
                    email='alice@example.com',
                ).ho_ainsert()
                await Post(
                    title='First post', content='Hello world',
                    author_id=alice['id'],
                ).ho_ainsert()
            # both rows are committed, or neither is
            ```

    *New in version 0.18.0.*
    """

    __transactions: dict = {}

    def __call__(self, model):
        transactions = self.__class__.__transactions
        self.__id = id(model)
        self.__transaction = None
        if self.__id not in transactions:
            transactions[self.__id] = {
                'level': 0, 'model': model,
                'sp_counter': 0, 'sp_stack': [],
            }
        self.__transaction = transactions[self.__id]

    __init__ = __call__

    async def __aenter__(self):
        conn = self.__transaction['model']._aconnection
        if conn.autocommit:
            await conn.set_autocommit(False)
        if self.__transaction['level'] > 0:
            self.__transaction['sp_counter'] += 1
            sp_name = f'sp_{self.__transaction["sp_counter"]}'
            self.__transaction['sp_stack'].append(sp_name)
            async with conn.cursor() as cur:
                await cur.execute(f'SAVEPOINT {sp_name}')
        self.__transaction['level'] += 1

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__transaction['level'] -= 1
        conn = self.__transaction['model']._aconnection
        if self.__transaction['level'] > 0:
            sp_name = self.__transaction['sp_stack'].pop()
            async with conn.cursor() as cur:
                if exc_type is not None:
                    await cur.execute(f'ROLLBACK TO SAVEPOINT {sp_name}')
                await cur.execute(f'RELEASE SAVEPOINT {sp_name}')
        else:
            try:
                await conn.commit()
                await conn.set_autocommit(True)
            except psycopg.Error:
                await conn.rollback()
        return False

    @property
    def level(self):
        return self.__transaction.get('level')

    def is_set(self):
        return self.__transaction.get('level', 0) > 0
