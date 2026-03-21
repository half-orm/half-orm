#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Thread-safety tests for Model._connection (per-thread lazy connections)."""

import queue
import threading
from unittest import TestCase

import psycopg2

from ..init import halftest, model
from half_orm.transaction import Transaction


def _run_in_thread(fn):
    """Run fn() in a new thread; propagate any exception back to the caller."""
    result_q = queue.Queue()

    def target():
        try:
            result_q.put(('ok', fn()))
        except Exception as exc:  # pylint: disable=broad-except
            result_q.put(('err', exc))

    t = threading.Thread(target=target)
    t.start()
    t.join()
    status, value = result_q.get()
    if status == 'err':
        raise value
    return value


class Test(TestCase):
    def test_threads_get_distinct_connections(self):
        "Each thread must receive its own psycopg2 connection object."
        conns = []
        lock = threading.Lock()

        def grab_conn():
            conn = model._connection
            with lock:
                conns.append(conn)

        t1 = threading.Thread(target=grab_conn)
        t2 = threading.Thread(target=grab_conn)
        t1.start(); t2.start()
        t1.join(); t2.join()

        self.assertEqual(len(conns), 2)
        self.assertIsNot(conns[0], conns[1])
        for conn in conns:
            self.assertEqual(conn.closed, 0)

    def test_thread_disconnect_does_not_affect_others(self):
        "disconnect() in one thread must not close other threads' connections."
        barrier = threading.Barrier(2)
        results = {}

        def thread_a():
            _ = model._connection
            barrier.wait()
            model.disconnect()

        def thread_b():
            _ = model._connection
            barrier.wait()
            import time; time.sleep(0.05)
            results['b'] = model.execute_query("select 1").fetchone()

        ta = threading.Thread(target=thread_a)
        tb = threading.Thread(target=thread_b)
        ta.start(); tb.start()
        ta.join(); tb.join()

        self.assertIsNotNone(results.get('b'))
        model.reconnect()

    def test_lazy_open_on_new_thread(self):
        "A new thread that never called reconnect() can execute queries."
        def query():
            return model.execute_query("select 1").fetchone()

        row = _run_in_thread(query)
        self.assertEqual(row['?column?'], 1)

    def test_ping_reconnects_current_thread(self):
        "ping() must re-open the current thread's connection when it is closed."
        def do_ping():
            model._connection.close()
            model.ping()
            return model.execute_query("select 1").fetchone()

        row = _run_in_thread(do_ping)
        self.assertEqual(row['?column?'], 1)

    def test_transaction_state_isolated_per_thread(self):
        "Transaction level must be independent in each thread."
        levels = {}
        barrier = threading.Barrier(2)

        def enter_transaction(name):
            with Transaction(model):
                levels[name] = Transaction(model).level
                barrier.wait()

        ta = threading.Thread(target=enter_transaction, args=('a',))
        tb = threading.Thread(target=enter_transaction, args=('b',))
        ta.start(); tb.start()
        ta.join(); tb.join()

        self.assertEqual(levels['a'], 1)
        self.assertEqual(levels['b'], 1)