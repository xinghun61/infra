# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import os
import unittest

from infra.tools.antibody import git_commit_parser


DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def read_data(data):
  with open(os.path.join(DATA_DIR, data), 'r') as f:
    return f.read()


class TestGitCommitParser(unittest.TestCase):
  def setUp(self):
    self.log = git_commit_parser.parse_commit_info(read_data(
                                                   'data/test_git_log.txt'))

  def test_parse_commit_info(self):
    self.assertEqual(type(self.log), list)
    self.assertEqual(type(self.log[0]), dict)

  def test_get_features_for_git_commit(self):
    mockCursor = mock.Mock()
    for commit in self.log:
      if commit['id'] == 'df88fd603ca6a3831b4f2b21156a3e0d93e30095':
        self.assertEqual(git_commit_parser.get_features_for_git_commit(commit,
                         'fake/path', mockCursor),
                        ('df88fd603ca6a3831b4f2b21156a3e0d93e30095', None,
                          '2012-11-13 15:13:54',
                          'https://codereview.appspot.com/6846046/', 0,
                          'Add new index to make sure the CQ never ever get '
                          'blocked again'))

  def test_get_features_for_commit_people(self):
    for commit in self.log:
      if commit['id'] == 'df88fd603ca6a3831b4f2b21156a3e0d93e30095':
        features = git_commit_parser.get_features_for_commit_people(commit)
        comparable_features = [(x[0], x[1], None, x[3]) for x in features]
    self.assertEqual(comparable_features,
                     [('maruel',
                       'df88fd603ca6a3831b4f2b21156a3e0d93e30095',
                       None, 'author'),
                      ('ilevy',
                       'df88fd603ca6a3831b4f2b21156a3e0d93e30095', None,
                       'tbr')])

  def test_parse_commit_people(self):
    commits = git_commit_parser.parse_commit_people(self.log)
    self.assertTrue(len(commits) > 0)