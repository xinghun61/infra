# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gitiles import GitilesCommit
from test import CrBuildTestCase
from gitiles.test.gitiles_client_stub import GitilesClientStub


class GitilesCommitTest(CrBuildTestCase):
  def test_get_change(self):
    hostname = 'chromium.googlesource.com'
    project = 'project'

    sha = GitilesClientStub.test_commit.sha
    commit = GitilesCommit.fetch(hostname, project, sha,
                                 client_factory=GitilesClientStub)
    self.assertIsNotNone(commit)
    expected_id = 'gitiles~%s~%s~%s' % (hostname, project, sha)
    self.assertEqual(commit.key.id(), expected_id)
    self.assertEqual(commit.hostname, hostname)
    self.assertEqual(commit.project, project)

    def test_contributor(actual, expected):
      self.assertIsNotNone(actual)
      self.assertEqual(actual.name, expected.name)
      self.assertEqual(actual.email, expected.email)
      self.assertEqual(actual.time, expected.time)
    test_contributor(commit.committer, GitilesClientStub.test_contributor)
    test_contributor(commit.author, GitilesClientStub.test_contributor)
