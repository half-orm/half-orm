#-*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods, protected-access

"""This module provides the Transaction class."""

import sys

import psycopg2

class Transaction:
    """
    """

    __transactions = {}
    def __call__(self, model):
        self.__id = id(model)
        self.__transaction = None
        if self.__id not in self.__class__.__transactions:
            self.__class__.__transactions[self.__id] = {}
            self.__transaction = self.__class__.__transactions[self.__id]
            self.__transaction['level'] = 0
            self.__transaction['model'] = model
            self.__transaction['sp_counter'] = 0
            self.__transaction['sp_stack'] = []
        else:
            self.__transaction = self.__transactions[self.__id]

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
            except psycopg2.Error:
                conn.rollback()
        return False

    @property
    def level(self):
        return self.__transaction.get('level')

    def is_set(self):
        return self.__transaction.get('level', 0) > 0
