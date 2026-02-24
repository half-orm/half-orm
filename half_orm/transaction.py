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
        else:
            self.__transaction = self.__transactions[self.__id]

    __init__ = __call__

    def __enter__(self):
        if self.__transaction['model']._connection.autocommit:
            self.__transaction['model']._connection.autocommit = False
        self.__transaction['level'] += 1

    def __exit__(self, *_):
        self.__transaction['level'] -= 1
        if self.__transaction['level'] == 0:
            try:
                self.__transaction['model']._connection.commit()
                self.__transaction['model']._connection.autocommit = True
            except psycopg2.Error:
                self.__transaction['model']._connection.rollback()

    @property
    def level(self):
        return self.__transaction.get('level')

    def is_set(self):
        return self.__transaction.get('level', 0) > 0
