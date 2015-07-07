# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool-specific testable functions for antibody."""

import argparse
import json
import os
import sqlite3

import infra_libs
from testing_support import auto_stub
from infra.tools.antibody import antibody
import infra.tools.antibody.cloudsql_connect as csql

THIS_DIR = os.path.dirname(os.path.realpath(__file__))


class MyTest(auto_stub.TestCase):
  def test_arguments(self):
    parser = argparse.ArgumentParser()
    antibody.add_argparse_options(parser)
    args = parser.parse_args(['--cache-path', '/ab', '--git-checkout-path',
                              '/bcd', '--sql-password-file', 'abd.txt',
                              '--write-html', '--run-antibody',
                              '--parse-git-rietveld'])
    self.assertEqual(args.cache_path, '/ab')
    self.assertEqual(args.git_checkout_path, '/bcd')
    self.assertEqual(args.sql_password_file, 'abd.txt')
    self.assertTrue(args.write_html)
    self.assertTrue(args.run_antibody)
    self.assertTrue(args.parse_git_rietveld)

    args = parser.parse_args(['-c', '/ab', '-g', '/bcd', '-p', 'abd.txt', '-w',
                              '-a', '-r'])
    self.assertEqual(args.cache_path, '/ab')
    self.assertEqual(args.git_checkout_path, '/bcd')
    self.assertEqual(args.sql_password_file, 'abd.txt')
    self.assertTrue(args.write_html)
    self.assertTrue(args.run_antibody)
    self.assertTrue(args.parse_git_rietveld)

  def test_generate_antibody_ui(self):
    with infra_libs.temporary_directory(prefix='antibody-test') as dirname:
      commit_data = 'data/sample_suspicious_commits.txt'
      with open(os.path.join(THIS_DIR, commit_data), 'r') as f:
        suspicious_commits_data = [line.rstrip('\n').split(',') for line in f]
      temp_data_gitiles="https://chromium.googlesource.com/infra/infra/+/"
      antibody.generate_antibody_ui(suspicious_commits_data, temp_data_gitiles,
                                    dirname)
      with open(
          os.path.join(dirname, antibody.ANTIBODY_UI_MAIN_NAME), 'r') as f:
        file_string = f.read()
        self.assertTrue(file_string)
        self.assertFalse('{{' in file_string)
        self.assertFalse('}}' in file_string)

      with open(os.path.join(dirname, antibody.TBR_BY_USER_NAME), 'r') as f:
        file_string = f.read()
        self.assertTrue(file_string)
        self.assertFalse('{{' in file_string)
        self.assertFalse('}}' in file_string)

  def test_get_tbr_by_user(self):
    with infra_libs.temporary_directory(prefix='antibody-test') as dirname:
      # set up fake db to read from
      file_name = os.path.join(dirname, 'antibody.db')
      with sqlite3.connect(file_name) as con:
        cur = con.cursor()
        cur.execute('CREATE TABLE %s (git_hash, lgtm, tbr, '
                    'review_url, request_timestamp, num_cced)'
                    % csql.DEFAULT_RIETVELD_TABLE)
        fake_rietveld_data = ( 
            (1, '1', '0', 'https://codereview.chromium.org/1158153006', 1, 1),
            (2, '0', '0', 'https://codereview.chromium.org/1175993003', 1, 1),
            (3, '1', '0', 'https://codereview.chromium.org/1146053009', 1, 1),
            (4, '0', '1', 'https://codereview.chromium.org/1004453003', 1, 1),
            (5, '0', '1', 'https://codereview.chromium.org/1171763002', 1, 1),
            (6, '1', '1', 'https://codereview.chromium.org/1175623002', 1, 1),
        )
        cur.executemany('INSERT INTO %s VALUES(?, ?, ?, ?, ?, ?)'
                        % csql.DEFAULT_RIETVELD_TABLE, fake_rietveld_data)

        cur.execute('CREATE TABLE %s (git_hash, bug_number, tbr, '
                    'review_url)'
                    % csql.DEFAULT_GIT_TABLE)
        fake_git_data = ( 
            (2, 123, 'pgervais@chromium.org,hinoka@chromium.org', 
             'https://codereview.chromium.org/1175993003'),
            (5, 456, 'hinoka@chromium.org,keelerh@google.com', 
             'https://codereview.chromium.org/1171763002'),
            (6, 789, '', 'https://codereview.chromium.org/1175623002'),
        )
        cur.executemany('INSERT INTO %s VALUES(?, ?, ?, ?)'
                        % csql.DEFAULT_GIT_TABLE, fake_git_data)

        antibody.get_tbr_by_user(cur, dirname)
        expected_out = {
          "by_user" : {
            "pgervais" : [[2, 'https://codereview.chromium.org/1175993003', 1]],
            "hinoka" : [[2, 'https://codereview.chromium.org/1175993003', 1],
                        [5, 'https://codereview.chromium.org/1171763002', 1]],
            "keelerh" : [[5, 'https://codereview.chromium.org/1171763002', 1]]
          },
          "gitiles_prefix" : "https://chromium.googlesource.com/infra/infra/+/",
        }
        with open(os.path.join(dirname, 'tbr_by_user.json'), 'r') as f:
          output = json.load(f)
          self.assertItemsEqual(output, expected_out)