# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sqlite3
import unittest

import infra_libs
from infra.tools.antibody import git_commit_parser


class TestGitCommitParser(unittest.TestCase):
  def test_create_table(self):
    with infra_libs.temporary_directory(prefix='rietveld-test') as dirname:
      file_name = os.path.join(dirname, 'rietveld_data.sqlite3')
      expected_table_headers = ('git_hash', 'bug_number', 'tbr', 'review_url')
      with sqlite3.connect(file_name) as con:
        cur = con.cursor()
        git_commit_parser.create_table(cur)
        cur.execute('PRAGMA TABLE_INFO(%s);'
                    % git_commit_parser.DEFAULT_TABLE_NAME)
        table_headers = cur.fetchall()
        for i in xrange(len(table_headers)):
          self.assertTrue(expected_table_headers[i] == table_headers[i][1])


  def test_get_urls_from_git_db(self):
    with infra_libs.temporary_directory(prefix='gitparser-test') as dirname:
      # set up fake db to read from
      file_name = os.path.join(dirname, 'infra_db.sqlite')
      with sqlite3.connect(file_name) as con:
        cur = con.cursor()
        cur.execute('CREATE TABLE %s (git_hash, bug_num, tbr, review_url)'
                    %git_commit_parser.DEFAULT_TABLE_NAME)
        fake_data = ( 
            ('a', 1, 'b', 'https://codereview.chromium.org/1158153006'),
            ('c', 2, 'd', 'https://codereview.chromium.org/1175993003'),
            ('e', 3, 'f', 'https://codereview.chromium.org/1146053009'),
        )
        cur.executemany('INSERT INTO %s VALUES(?, ?, ?, ?)'
                        %git_commit_parser.DEFAULT_TABLE_NAME, fake_data)

      expected_out = (
            'https://codereview.chromium.org/1158153006',
            'https://codereview.chromium.org/1175993003',
            'https://codereview.chromium.org/1146053009',
      )
      out = git_commit_parser.get_urls_from_git_db(file_name)
      for i in xrange(len(out)):
        self.assertEqual(expected_out[i], out[i])
