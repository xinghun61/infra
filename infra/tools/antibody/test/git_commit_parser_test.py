# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sqlite3
import unittest

import infra_libs
import infra.tools.antibody.cloudsql_connect as csql
from infra.tools.antibody import git_commit_parser


DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def read_data(data):
  with open(os.path.join(DATA_DIR, data), 'r') as f:
    return f.read()

class TestGitCommitParser(unittest.TestCase):
  def setUp(self):
    self.log = git_commit_parser.parse_commit_info(read_data(
                                                   'data/git_log.txt'))

  def test_parse_commit_info(self):
    self.assertEqual(type(self.log), list)
    self.assertEqual(type(self.log[0]), dict)

  def test_is_commit_suspicious(self):
    for commit in self.log:
      if commit['id'] == '82a0607dd2ad23ea5859c0e0deccd75bbc691ece':
        self.assertFalse(git_commit_parser.is_commit_suspicious(commit))
      elif commit['id'] == 'df88fd603ca6a3831b4f2b21156a3e0d93e30096':
        self.assertFalse(git_commit_parser.is_commit_suspicious(commit))
      else:
        self.assertTrue(git_commit_parser.is_commit_suspicious(commit))

  def test_get_features_from_commit(self):
    for commit in self.log:
      if commit['id'] == 'df88fd603ca6a3831b4f2b21156a3e0d93e30095':
        self.assertEqual(git_commit_parser.get_features_from_commit(commit),
                        ('df88fd603ca6a3831b4f2b21156a3e0d93e30095', None,
                         'ilevy@chromium.org',
                         'https://codereview.appspot.com/6846046/'))

  def test_parse_commit_message(self):
    commits = git_commit_parser.parse_commit_message(self.log)
    self.assertTrue(len(commits) > 0)

  def test_get_urls_from_git_db(self):
    with infra_libs.temporary_directory(prefix='gitparser-test') as dirname:
      # set up fake db to read from
      file_name = os.path.join(dirname, 'infra_db.sqlite')
      with sqlite3.connect(file_name) as con:
        cur = con.cursor()
        cur.execute('CREATE TABLE %s (git_hash, bug_num, tbr, review_url)'
                    % csql.DEFAULT_GIT_TABLE)
        fake_data = (
            ('a', 1, 'b', 'https://codereview.chromium.org/1158153006'),
            ('c', 2, 'd', ''),
            ('e', 3, 'f', 'https://codereview.chromium.org/1146053009'),
        )
        cur.executemany('INSERT INTO %s VALUES(?, ?, ?, ?)'
                        % csql.DEFAULT_GIT_TABLE, fake_data)

        expected_out = (
              ('a', 'https://codereview.chromium.org/1158153006'),
              ('e', 'https://codereview.chromium.org/1146053009'),
        )
        out = git_commit_parser.get_urls_from_git_db(cur)
        for i in xrange(len(out)):
          self.assertEqual(expected_out[i], out[i])
