# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for credentials.py"""

import mock
import tempfile
import unittest

from infra.libs import gerrit_api


GIT_COOKIE_FILE = ('# HTTP Cookie File\n.googlesource.com\tTRUE\t/\tTRUE\t'
                   '2147483647\to\tgit-commit-bot@chromium.org=secret\n'
                   'wrong.entry/\to\na\tb\t/\tc\t1\td\ta@b.org\n')
GIT_COOKIE_FILE_PARSE_ERROR = '.com\tTRUE\t/\tTRUE\t1\to\ta@c.org\n'
NETRC_FILE = ('machine chromium.googlesource.com '
              'login git-commit-bot@chromium.org password secret')


class CredentialsTestCase(unittest.TestCase):

  def setUp(self):
    self.gitcookie_file = tempfile.NamedTemporaryFile()
    self.gitcookie_file.write(GIT_COOKIE_FILE)
    self.gitcookie_file.flush()
    self.gitcookie_file_wrong = tempfile.NamedTemporaryFile()
    self.gitcookie_file_wrong.write(GIT_COOKIE_FILE_PARSE_ERROR)
    self.gitcookie_file_wrong.flush()
    self.netrc_file = tempfile.NamedTemporaryFile()
    self.netrc_file.write(NETRC_FILE)
    self.netrc_file.flush()

  def tearDown(self):
    self.gitcookie_file.close()
    self.gitcookie_file_wrong.close()
    self.netrc_file.close()

  def test_load_gitcookie_file(self):
    creds = gerrit_api.load_gitcookie_file(self.gitcookie_file.name)
    creds_expected = {
        '.googlesource.com' : ('git-commit-bot@chromium.org', 'secret')
    }
    self.assertEqual(creds, creds_expected)

  def test_load_netrc_file(self):
    netrc = gerrit_api.load_netrc_file(self.netrc_file.name)
    self.assertEqual(netrc.authenticators('chromium.googlesource.com'),
                     ('git-commit-bot@chromium.org', None, 'secret'))

  def test_load_netrc_file_wrong_path(self):
    self.assertRaises(gerrit_api.NetrcException,
                      gerrit_api.load_netrc_file, 'wrong')

  def test_load_gitcookie_file_wrong_path(self):
    self.assertRaises(gerrit_api.GitcookiesException,
                      gerrit_api.load_gitcookie_file, 'wrong')

  def test_load_gitcookie_file_parse_error(self):
    self.assertRaises(gerrit_api.GitcookiesException,
                      gerrit_api.load_gitcookie_file,
                      self.gitcookie_file_wrong.name)

  def test_getitem_with_netrc(self):
    creds = gerrit_api.Credentials(
        netrc_path=self.netrc_file.name)
    auth = creds['chromium.googlesource.com']
    self.assertEqual(auth, ('git-commit-bot@chromium.org', 'secret'))

  def test_getitem_with_gitcookies(self):
    creds = gerrit_api.Credentials(gitcookies_path=self.gitcookie_file.name)
    auth = creds['chromium.googlesource.com']
    self.assertEqual(auth, ('git-commit-bot@chromium.org', 'secret'))

  def test_getitem_no_credentials(self):
    creds = gerrit_api.Credentials(
        netrc_path=self.netrc_file.name,
        gitcookies_path=self.gitcookie_file.name)
    self.assertRaises(KeyError, creds.__getitem__, 'some.other.host.com')

  def test_mock_credentials(self):
    creds = gerrit_api.Credentials(
        auth=('git-commit-bot@chromium.org', 'secret'))
    self.assertEqual(creds['whatever.com'],
                     ('git-commit-bot@chromium.org', 'secret'))
