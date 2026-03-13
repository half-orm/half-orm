#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

import contextlib
import io
import re
import sys
from half_orm.hotest import HoTestCase

from ..init import halftest

expected = re.compile(r"""select r\d+\.\* from "blog"\."post" as r\d+""")

class Test(HoTestCase):
    def setUp(self):
        self.pers = halftest.person_cls()
        self.post = halftest.post_cls()

    def test_mogrify(self):
        "it should print the SQL query"
        self.post.ho_mogrify()
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            list(self.post.ho_select())
            value = re.sub(r'\s+', ' ', f.getvalue().replace('\n', ' ').replace('  ', ' '))
            self.assertTrue(re.match(expected, value) is not None)
