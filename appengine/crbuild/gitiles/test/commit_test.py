# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from mock import Mock

from gitiles import GitilesCommit
from test import CrBuildTestCase
from gitiles.test.gitiles_client_stub import GitilesClientStub


HOSTNAME = 'chromium.googlesource.com'
PROJECT = 'project'
REVISION = GitilesClientStub.test_commit.sha


class GitilesCommitTest(CrBuildTestCase):
  def test_get_change(self):
    commit = GitilesCommit.fetch(HOSTNAME, PROJECT, REVISION,
                                 client_factory=GitilesClientStub)
    self.assertIsNotNone(commit)
    expected_id = 'gitiles~%s~%s~%s' % (HOSTNAME, PROJECT, REVISION)
    self.assertEqual(commit.key.id(), expected_id)
    self.assertEqual(commit.hostname, HOSTNAME)
    self.assertEqual(commit.project, PROJECT)
    self.assertEqual(commit.revision, REVISION)
    self.assertEqual(commit.repo_url, 'https://%s/%s' % (HOSTNAME, PROJECT))
    self.assertEqual(commit.viewable_url, ('https://%s/%s/+/%s' %
                                           (HOSTNAME, PROJECT, REVISION)))
    self.assertEqual(commit.guess_gerrit_hostname(),
                     'chromium-review.googlesource.com')

    def test_contributor(actual, expected):
      self.assertIsNotNone(actual)
      self.assertEqual(actual.name, expected.name)
      self.assertEqual(actual.email, expected.email)
      self.assertEqual(actual.time, expected.time)
    test_contributor(commit.committer, GitilesClientStub.test_contributor)
    test_contributor(commit.author, GitilesClientStub.test_contributor)

  def test_get_change_twice_returns_same(self):
    def fetch_commit():
      return GitilesCommit.fetch(HOSTNAME, PROJECT, REVISION,
                                 client_factory=GitilesClientStub)
    self.assertEqual(fetch_commit(), fetch_commit())

  def test_get_nonexistent_change(self):
    client = Mock()
    client.get_commit.return_value = None
    commit = GitilesCommit.fetch(HOSTNAME, 'wrong project', REVISION,
                                 client_factory=lambda hostname: client)
    self.assertIsNone(commit)
