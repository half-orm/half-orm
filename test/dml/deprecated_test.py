import os
import pytest
from unittest import TestCase, skip

import pytest
from ..init import halftest

CURDIR = os.path.abspath(os.path.curdir)

ERR_MSG = f'''HalfORM WARNING! "\x1b[1mselect\x1b[0m" is deprecated. It will be removed in half_orm 1.0.
Use "\x1b[1mho_select\x1b[0m" instead.
{CURDIR}/test/dml/deprecated_test.py:18, in test_deprecated
    halftest.person_cls(last_name='aabc', first_name='aabc', birth_date='1997-01-03').select()

'''

@skip
def test_deprecated(capsys):
    "use of select should print a warning on stderr"
    halftest.person_cls(last_name='aabc', first_name='aabc', birth_date='1997-01-03').select()
    _, err = capsys.readouterr()
    TestCase().assertEqual(err, ERR_MSG)
