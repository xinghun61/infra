# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Gitiles client for GAE environment."""

from datetime import datetime

from gitiles.client import GitContributor, Commit


# pylint: disable=W0613, W0622, R0201
class GitilesClientStub(object):
  def __init__(self, *args, **kwargs):
    pass

  test_contributor = GitContributor(
      name='John Doe',
      email='john.doe@chromium.org',
      time=datetime(2014, 1, 1),
  )
  test_commit = Commit(
      sha='aaaaabbbbbaaaaabbbbbaaaaabbbbbaaaaabbbbb',
      tree='1aaaabbbbbaaaaabbbbbaaaaabbbbbaaaaabbbbb',
      parents=['2aaaabbbbbaaaaabbbbbaaaaabbbbbaaaaabbbbb'],
      author=test_contributor,
      committer=test_contributor,
      message='Subject\n\nBody',
  )
  test_commit2 = Commit(
      sha='cccccdddddcccccdddddcccccdddddcccccddddd',
      tree='1ccccdddddcccccdddddcccccdddddcccccddddd',
      parents=['2aaaabbbbbaaaaabbbbbaaaaabbbbbaaaaabbbbb'],
      author=test_contributor,
      committer=test_contributor,
      message='Subject2\n\nBody2',
  )

  def get_commit(self, project, commit_sha):
    if commit_sha == self.test_commit.sha:
      return self.test_commit
    else:
      return self.test_commit2
