#-*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods, protected-access

"""This module provides the Transaction class."""

import inspect
import sys
import threading
import traceback

import psycopg

from half_orm import utils

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

        Work that must wait for the COMMIT (see :meth:`after_commit`):
            ```python
            with Transaction(blog):
                post = Post(title='First post').ho_insert()
                Transaction(blog).after_commit(lambda: notify(post['id']))
            # notify() runs here, the COMMIT having succeeded
            ```

    *New in version 0.18.0:* nested ``Transaction`` blocks use savepoints.

    *New in version 1.2.0:* :meth:`after_commit` and :meth:`after_rollback`.
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
                'on_commit': [], 'on_rollback': [],
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
        # One frame of callbacks per open scope. Pushed last: nothing may fail
        # after this point, or `__exit__` would never pop them.
        self.__transaction['on_commit'].append([])
        self.__transaction['on_rollback'].append([])

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__transaction['level'] -= 1
        conn = self.__transaction['model']._connection
        on_commit = self.__transaction['on_commit'].pop()
        on_rollback = self.__transaction['on_rollback'].pop()
        if self.__transaction['level'] > 0:
            sp_name = self.__transaction['sp_stack'].pop()
            with conn.cursor() as cur:
                if exc_type is not None:
                    cur.execute(f'ROLLBACK TO SAVEPOINT {sp_name}')
                cur.execute(f'RELEASE SAVEPOINT {sp_name}')
            self.__settle(exc_type is None, on_commit, on_rollback)
        else:
            committed = False
            try:
                if exc_type is not None:
                    conn.rollback()
                else:
                    conn.commit()
                    committed = True
            except psycopg.Error:
                # A failed COMMIT must reach the caller: silently rolling back
                # would leave the application believing its work was persisted.
                # A failed ROLLBACK, on the other hand, must not displace the
                # exception the caller is already handling.
                if exc_type is None:
                    raise
            finally:
                _restore_autocommit(conn)
                # In the `finally`: the callbacks of a transaction whose COMMIT
                # failed are those of a rollback, and they must run on the way
                # out of the error too.
                self.__settle(committed, on_commit, on_rollback)
        return False

    def after_commit(self, callback):
        """Register `callback` to run once the transaction has committed.

        A mutation only becomes a fact when the COMMIT succeeds: anything
        whose effect leaves the database — a notification, a cache eviction,
        a websocket event — has to wait for it, or it announces rows that a
        rollback has taken back.

        Outside a transaction, a mutation commits on its own and the callback
        runs immediately. Inside one, it is queued and runs after the COMMIT
        of the outermost block, in registration order, with the connection
        back in autocommit mode. Rolling back a savepoint drops the callbacks
        registered inside it; releasing one hands them to the enclosing scope,
        whose own outcome then decides.

        Registration is bound to the model and the current thread, not to this
        instance: ``Transaction(model).after_commit(...)`` reaches the open
        transaction from anywhere in the call stack, with no reference to the
        object that opened it.

        A callback failure is reported on stderr, and the callbacks that
        follow still run. It is never raised to the caller: the COMMIT has
        already succeeded, and an exception here would describe the
        transaction as having failed.

        Args:
            callback: a callable taking no argument. Its return value is
                ignored.

        Example:
            Publish an event only if the whole unit of work lands:
                ```python
                @transaction
                def publish(self, title):
                    post = self.post_rfk(title=title).ho_insert()
                    Transaction(self._ho_model).after_commit(
                        lambda: broadcast('post', 'create', post['id']))
                    self.index(post)       # may raise — nothing is broadcast
                ```

        *New in version 1.2.0.*
        """
        frames = self.__transaction['on_commit']
        if frames:
            frames[-1].append(callback)
        else:
            _run_callbacks([callback])

    def after_rollback(self, callback):
        """Register `callback` to run if the transaction is rolled back.

        The mirror of :meth:`after_commit`: the callback runs when the scope
        it was registered in is undone — the rollback of the outermost block,
        the rollback of the savepoint it belongs to, or a COMMIT that fails.
        Releasing a savepoint hands its callbacks to the enclosing scope,
        which may still roll back.

        Outside a transaction there is nothing to undo and the callback is
        dropped — the symmetric case of :meth:`after_commit` running it at
        once.

        As with :meth:`after_commit`, a callback failure is reported on stderr
        and never raised: here it would displace the exception the caller is
        already handling.

        Args:
            callback: a callable taking no argument. Its return value is
                ignored.

        *New in version 1.2.0.*
        """
        frames = self.__transaction['on_rollback']
        if frames:
            frames[-1].append(callback)

    def __settle(self, committed, on_commit, on_rollback):
        """Dispose of the callbacks of the scope that just ended.

        A released savepoint hands them to the enclosing scope instead of
        running them: nothing is committed until the outermost block is.
        """
        enclosing = self.__transaction['on_commit']
        if committed and enclosing:
            enclosing[-1].extend(on_commit)
            self.__transaction['on_rollback'][-1].extend(on_rollback)
        elif committed:
            _run_callbacks(on_commit)
        else:
            _run_callbacks(on_rollback)

    @property
    def level(self):
        return self.__transaction.get('level')

    def is_set(self):
        return self.__transaction.get('level', 0) > 0


def _restore_autocommit(conn):
    """Put `conn` back in autocommit mode after the outermost block.

    Best-effort: if the connection is broken, the failure is irrelevant here —
    ``Model._connection`` reconnects on the next use — and must not mask the
    exception on its way out of ``__exit__``.
    """
    try:
        conn.autocommit = True
    except psycopg.Error:
        pass


async def _arestore_autocommit(conn):
    "Async counterpart of :func:`_restore_autocommit`."
    try:
        await conn.set_autocommit(True)
    except psycopg.Error:
        pass


def _run_callbacks(callbacks):
    """Run each callback in registration order, reporting any failure.

    A callback must not raise here: the outcome of the transaction is already
    decided, and the exception would misrepresent it — as a failure after a
    successful COMMIT, or in place of the error being handled after a
    rollback. Each failure is reported on stderr and the callbacks that follow
    still run: one broken listener must not silence the others.
    """
    for callback in callbacks:
        try:
            callback()
        except Exception:  # pylint: disable=broad-except
            _report_failure(callback)


async def _arun_callbacks(callbacks):
    """Async counterpart of :func:`_run_callbacks`.

    Awaits whatever a callback returns, so a coroutine function and a plain
    one are both acceptable.
    """
    for callback in callbacks:
        try:
            result = callback()
            if inspect.isawaitable(result):
                await result
        except Exception:  # pylint: disable=broad-except
            _report_failure(callback)


def _report_failure(callback):
    "Report on stderr the failure of a transaction callback."
    name = getattr(callback, '__qualname__', None) or repr(callback)
    utils.warning(f'{name} transaction callback failed:\n{traceback.format_exc()}')


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

    *New in version 1.2.0:* :meth:`after_commit` and :meth:`after_rollback`.
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
                'on_commit': [], 'on_rollback': [],
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
        # See Transaction.__enter__: one frame per open scope, pushed last.
        self.__transaction['on_commit'].append([])
        self.__transaction['on_rollback'].append([])

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__transaction['level'] -= 1
        conn = self.__transaction['model']._aconnection
        on_commit = self.__transaction['on_commit'].pop()
        on_rollback = self.__transaction['on_rollback'].pop()
        if self.__transaction['level'] > 0:
            sp_name = self.__transaction['sp_stack'].pop()
            async with conn.cursor() as cur:
                if exc_type is not None:
                    await cur.execute(f'ROLLBACK TO SAVEPOINT {sp_name}')
                await cur.execute(f'RELEASE SAVEPOINT {sp_name}')
            await self.__settle(exc_type is None, on_commit, on_rollback)
        else:
            committed = False
            try:
                if exc_type is not None:
                    await conn.rollback()
                else:
                    await conn.commit()
                    committed = True
            except psycopg.Error:
                # See Transaction.__exit__ for why COMMIT and ROLLBACK
                # failures are treated differently.
                if exc_type is None:
                    raise
            finally:
                await _arestore_autocommit(conn)
                await self.__settle(committed, on_commit, on_rollback)
        return False

    async def after_commit(self, callback):
        """Register `callback` to run once the transaction has committed.

        Async counterpart of :meth:`Transaction.after_commit`, with the same
        semantics: queued inside a transaction and run after the COMMIT of
        the outermost block in registration order, dropped by the rollback of
        the savepoint it belongs to, handed to the enclosing scope when that
        savepoint is released.

        Awaiting registration is what lets the callback run outside any
        transaction: there is nothing to defer it to, so it runs — and is
        awaited — on the spot, rather than becoming a background task nobody
        holds a reference to.

        Args:
            callback: a callable taking no argument, coroutine function or
                not. What it returns is awaited if awaitable, and otherwise
                ignored.

        Example:
            Publish an event only if the whole unit of work lands:
                ```python
                async with AsyncTransaction(blog):
                    post = await Post(title='First post').ho_ainsert()
                    await AsyncTransaction(blog).after_commit(
                        lambda: publish('post', 'create', post['id']))
                ```

        *New in version 1.2.0.*
        """
        frames = self.__transaction['on_commit']
        if frames:
            frames[-1].append(callback)
        else:
            await _arun_callbacks([callback])

    async def after_rollback(self, callback):
        """Register `callback` to run if the transaction is rolled back.

        Async counterpart of :meth:`Transaction.after_rollback`, with the same
        semantics. A coroutine like :meth:`after_commit`, for symmetry — it
        has nothing to await, a callback registered outside a transaction
        being dropped.

        Args:
            callback: a callable taking no argument, coroutine function or
                not. What it returns is awaited if awaitable, and otherwise
                ignored.

        *New in version 1.2.0.*
        """
        frames = self.__transaction['on_rollback']
        if frames:
            frames[-1].append(callback)

    async def __settle(self, committed, on_commit, on_rollback):
        """Dispose of the callbacks of the scope that just ended.

        Async counterpart of ``Transaction.__settle``: a released savepoint
        hands them to the enclosing scope instead of running them.
        """
        enclosing = self.__transaction['on_commit']
        if committed and enclosing:
            enclosing[-1].extend(on_commit)
            self.__transaction['on_rollback'][-1].extend(on_rollback)
        elif committed:
            await _arun_callbacks(on_commit)
        else:
            await _arun_callbacks(on_rollback)

    @property
    def level(self):
        return self.__transaction.get('level')

    def is_set(self):
        return self.__transaction.get('level', 0) > 0
