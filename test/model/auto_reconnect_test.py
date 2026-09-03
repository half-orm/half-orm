#!/usr/bin/env python3
#-*- coding:  utf-8 -*-

import shutil
import subprocess
import unittest
from unittest import TestCase

from ..init import halftest

def _can_restart_postgresql():
    "True if this environment can non-interactively restart the postgresql service"
    if not (shutil.which("sudo") and shutil.which("service")):
        return False
    return subprocess.run(
        ["sudo", "-n", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0

class Test(TestCase):
    def setUp(self):
        self.pers = halftest.person_cls()

    @unittest.skipUnless(
        _can_restart_postgresql(),
        "requires passwordless sudo and the `service` command (see .gitlab-ci.yml / python-package.yml)")
    def test_automatic_reconnection(self):
        "it should reconnect after postgresql has been restarted"
        subprocess.run(["sudo", "service", "postgresql", "restart"], check=True)
        list(self.pers())
