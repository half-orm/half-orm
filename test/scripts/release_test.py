#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for scripts/do_release.py."""

import io
import json
import subprocess
import sys
import unittest.mock as mock
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parent.parent.parent

# Import helpers directly — they have no side effects at import time.
sys.path.insert(0, str(ROOT))
from scripts.do_release import (
    _clean_decoration,
    _github_repo,
    check_github_ci,
    parse_major_minor,
    generate_log,
    current_version,
    last_tag,
)


class TestCleanDecoration(TestCase):
    def test_standalone_head(self):
        line = '* feat: something (HEAD -> main) (abc1234)'
        self.assertEqual(_clean_decoration(line),
                         '* feat: something (abc1234)')

    def test_head_combined_with_tag(self):
        line = '* feat: something (HEAD -> main, tag: v1.0.0rc1) (abc1234)'
        self.assertEqual(_clean_decoration(line),
                         '* feat: something (tag: v1.0.0rc1) (abc1234)')

    def test_tag_only(self):
        line = '* fix: patch (tag: v0.18.13) (abc1234)'
        self.assertEqual(_clean_decoration(line),
                         '* fix: patch (tag: v0.18.13) (abc1234)')

    def test_plain_commit(self):
        line = '* fix: plain commit (abc1234)'
        self.assertEqual(_clean_decoration(line), '* fix: plain commit (abc1234)')

    def test_no_decoration(self):
        line = '* docs: update README (def5678)'
        self.assertEqual(_clean_decoration(line), line)


class TestParseMajorMinor(TestCase):
    def test_stable(self):
        self.assertEqual(parse_major_minor('1.2.3'), ('1', '2'))

    def test_rc(self):
        self.assertEqual(parse_major_minor('1.0.0rc1'), ('1', '0'))

    def test_alpha(self):
        self.assertEqual(parse_major_minor('2.1.0a1'), ('2', '1'))

    def test_invalid(self):
        self.assertEqual(parse_major_minor('invalid'), (None, None))


class TestDryRun(TestCase):
    """Run the script in --dry-run mode and check output."""

    def _run_dry(self, new_version: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, 'scripts/do_release.py', '--dry-run'],
            cwd=ROOT,
            input=new_version + '\n',
            capture_output=True,
            text=True,
        )

    def test_dry_run_exits_zero(self):
        r = self._run_dry('1.0.0')
        self.assertEqual(r.returncode, 0, msg=r.stderr)

    def test_dry_run_shows_current_version(self):
        old = current_version()
        r = self._run_dry('1.0.0')
        self.assertIn(old, r.stdout)

    def test_dry_run_shows_new_version(self):
        r = self._run_dry('9.9.9')
        self.assertIn('9.9.9', r.stdout)

    def test_dry_run_does_not_modify_version_txt(self):
        old = current_version()
        self._run_dry('9.9.9')
        self.assertEqual(current_version(), old)

    def test_dry_run_shows_branch_when_minor_changes(self):
        old = current_version()
        old_maj, old_min = parse_major_minor(old)
        new_min = str(int(old_min) + 1)
        new_version = f'{old_maj}.{new_min}.0'
        r = self._run_dry(new_version)
        self.assertIn(f'{old_maj}.{old_min}', r.stdout)

    def test_dry_run_no_branch_when_patch_only(self):
        old = current_version()
        old_maj, old_min = parse_major_minor(old)
        new_version = f'{old_maj}.{old_min}.99'
        r = self._run_dry(new_version)
        self.assertNotIn('maintenance branch', r.stdout)

    def test_dry_run_shows_dry_run_label(self):
        r = self._run_dry('1.0.0')
        self.assertIn('DRY RUN', r.stdout)


class TestGithubRepo(TestCase):
    def test_https_url(self):
        with mock.patch('scripts.do_release.git') as mock_git:
            mock_git.return_value = mock.Mock(
                stdout='https://github.com/half-orm/half-orm.git\n')
            self.assertEqual(_github_repo(), 'half-orm/half-orm')

    def test_ssh_url(self):
        with mock.patch('scripts.do_release.git') as mock_git:
            mock_git.return_value = mock.Mock(
                stdout='git@github.com:half-orm/half-orm.git\n')
            self.assertEqual(_github_repo(), 'half-orm/half-orm')


class TestCheckGithubCI(TestCase):
    def _mock_response(self, runs):
        payload = json.dumps({'check_runs': runs}).encode()
        resp = mock.MagicMock()
        resp.read.return_value = payload
        resp.__enter__ = lambda s: s
        resp.__exit__ = mock.Mock(return_value=False)
        return resp

    def test_all_success(self):
        runs = [{'name': 'tests', 'conclusion': 'success'}]
        with mock.patch('scripts.do_release._github_repo', return_value='o/r'), \
             mock.patch('urllib.request.urlopen', return_value=self._mock_response(runs)):
            check_github_ci('abc1234')  # should not raise

    def test_failing_check_exits(self):
        runs = [{'name': 'tests', 'conclusion': 'failure'}]
        with mock.patch('scripts.do_release._github_repo', return_value='o/r'), \
             mock.patch('urllib.request.urlopen', return_value=self._mock_response(runs)):
            with self.assertRaises(SystemExit) as ctx:
                check_github_ci('abc1234')
            self.assertIn('tests', str(ctx.exception))

    def test_pending_check_exits(self):
        runs = [{'name': 'lint', 'conclusion': None}]
        with mock.patch('scripts.do_release._github_repo', return_value='o/r'), \
             mock.patch('urllib.request.urlopen', return_value=self._mock_response(runs)):
            with self.assertRaises(SystemExit):
                check_github_ci('abc1234')

    def test_no_runs_exits(self):
        with mock.patch('scripts.do_release._github_repo', return_value='o/r'), \
             mock.patch('urllib.request.urlopen', return_value=self._mock_response([])):
            with self.assertRaises(SystemExit) as ctx:
                check_github_ci('abc1234')
            self.assertIn('no CI', str(ctx.exception))