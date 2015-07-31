# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool-specific testable functions for antibody."""

import argparse
import datetime
import json
import mock
import os

import infra_libs
from testing_support import auto_stub
from infra.tools.antibody import antibody

THIS_DIR = os.path.dirname(os.path.realpath(__file__))


class MyTest(auto_stub.TestCase):
  def test_arguments(self):
    parser = argparse.ArgumentParser()
    antibody.add_argparse_options(parser)
    args = parser.parse_args(['--cache-path', '/ab', '--git-checkout-path',
        '/bcd', '--sql-password-file', 'abd.txt','--write-html', 
        '--run-antibody', '--parse-git-rietveld', '--output-dir-path',
        '/efg', '--since', '2000'])
    self.assertEqual(args.cache_path, '/ab')
    self.assertEqual(args.git_checkout_path, '/bcd')
    self.assertEqual(args.sql_password_file, 'abd.txt')
    self.assertTrue(args.write_html)
    self.assertTrue(args.run_antibody)
    self.assertTrue(args.parse_git_rietveld)
    self.assertEqual(args.output_dir_path, '/efg')
    self.assertEqual(args.since, '2000')

    args = parser.parse_args(['-c', '/ab', '-g', '/bcd', '-p', 'abd.txt', '-w',
                              '-a', '-r', '-d', '/efg', '-s', '2000'])
    self.assertEqual(args.cache_path, '/ab')
    self.assertEqual(args.git_checkout_path, '/bcd')
    self.assertEqual(args.sql_password_file, 'abd.txt')
    self.assertTrue(args.write_html)
    self.assertTrue(args.run_antibody)
    self.assertTrue(args.parse_git_rietveld)
    self.assertEqual(args.output_dir_path, '/efg')
    self.assertEqual(args.since, '2000')

  @mock.patch('infra.tools.antibody.antibody.generate_stats_files')
  @mock.patch('infra.tools.antibody.antibody.get_tbr_by_user')
  @mock.patch('infra.tools.antibody.code_review_parse.get_tbr_no_lgtm')
  def test_generate_antibody_ui(self, mock_tbr_by_user, 
                                mock_gen_stats, mock_tbr_no_lgtm):
    #pylint: disable=W0613
    fake_cc = None
    with infra_libs.temporary_directory(prefix='antibody-test') as dirname:
      commit_data = 'data/sample_suspicious_commits.txt'
      with open(os.path.join(THIS_DIR, commit_data), 'r') as f:
        suspicious_commits_data = [line.rstrip('\n').split(',') for line in f]
      temp_data_gitiles="https://chromium.googlesource.com/infra/infra/+/"
      sample_monthly_stats = {
        '7_days': {
          'suspicious_to_total_ratio': 1,
          'total_commits': 2,
          'tbr_no_lgtm': 3,
          'no_review_url': 4,
          'blank_tbr': 5,
          'tbr_no_lgtm_commits': [
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 1", "123456789abcdefghijklmnop"], 
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 2", "123456789abcdefghijklmnop"], 
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 3", "123456789abcdefghijklmnop"], ],
          'no_review_url_commits': [
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 1", "123456789abcdefghijklmnop"], 
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 3", "123456789abcdefghijklmnop"], ],
          'blank_tbr_commits': [
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 3", "123456789abcdefghijklmnop"], ],
        },
        '30_days': {
          'suspicious_to_total_ratio': 1,
          'total_commits': 2,
          'tbr_no_lgtm': 3,
          'no_review_url': 4,
          'blank_tbr': 5,
          'tbr_no_lgtm_commits': [
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 1", "123456789abcdefghijklmnop"], 
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 2", "123456789abcdefghijklmnop"], 
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 3", "123456789abcdefghijklmnop"], ],
          'no_review_url_commits': [
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 1", "123456789abcdefghijklmnop"], 
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 3", "123456789abcdefghijklmnop"], ],
          'blank_tbr_commits': [
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 3", "123456789abcdefghijklmnop"], ],
        },
        'all_time': {
          'suspicious_to_total_ratio': 1,
          'total_commits': 2,
          'tbr_no_lgtm': 3,
          'no_review_url': 4,
          'blank_tbr': 5,
          'tbr_no_lgtm_commits': [
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 1", "123456789abcdefghijklmnop"], 
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 2", "123456789abcdefghijklmnop"], 
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 3", "123456789abcdefghijklmnop"], ],
          'no_review_url_commits': [
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 1", "123456789abcdefghijklmnop"], 
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 3", "123456789abcdefghijklmnop"], ],
          'blank_tbr_commits': [
              ["https://codereview.chromium.org/", "2015-07-13 11:11:11", 
               "Fake Commit Subject 3", "123456789abcdefghijklmnop"], ],
        },
      }
      
      proj_dirname = os.path.join(dirname, 'proj')
      os.makedirs(proj_dirname)
      with open(os.path.join(proj_dirname,
                             'all_monthly_stats.json'), 'w') as f:
        json.dump(sample_monthly_stats, f)
      antibody.generate_antibody_ui(fake_cc, temp_data_gitiles, 'proj', '2014',
                                    dirname, suspicious_commits_data)
      
      with open(
          os.path.join(proj_dirname, antibody.ANTIBODY_UI_MAIN_NAME), 'r') as f:
        file_string = f.read()
        self.assertTrue(file_string)
        self.assertFalse('{{' in file_string)
        self.assertFalse('}}' in file_string)

      with open(os.path.join(proj_dirname,
                             antibody.TBR_BY_USER_NAME), 'r') as f:
        file_string = f.read()
        self.assertTrue(file_string)
        self.assertFalse('{{' in file_string)
        self.assertFalse('}}' in file_string)
        
      with open(os.path.join(proj_dirname, antibody.STATS_NAME), 'r') as f:
        file_string = f.read()
        self.assertTrue(file_string)
        self.assertFalse('{{' in file_string)
        self.assertFalse('}}' in file_string)
        
      with open(os.path.join(proj_dirname, 
                             antibody.LEADERBOARD_NAME), 'r') as f:
        file_string = f.read()
        self.assertTrue(file_string)
        self.assertFalse('{{' in file_string)
        self.assertFalse('}}' in file_string)

      with open(os.path.join(proj_dirname, antibody.STATS_7_NAME), 'r') as f:
        file_string = f.read()
        self.assertTrue(file_string)
        self.assertFalse('{{' in file_string)
        self.assertFalse('}}' in file_string)

      with open(os.path.join(proj_dirname, antibody.STATS_30_NAME), 'r') as f:
        file_string = f.read()
        self.assertTrue(file_string)
        self.assertFalse('{{' in file_string)
        self.assertFalse('}}' in file_string)

      with open(os.path.join(proj_dirname, 
                             antibody.STATS_ALL_TIME_NAME), 'r') as f:
        file_string = f.read()
        self.assertTrue(file_string)
        self.assertFalse('{{' in file_string)
        self.assertFalse('}}' in file_string)

      self.assertTrue(os.path.exists(os.path.join(dirname, 'static')))

  def test_get_tbr_by_user(self):
    with infra_libs.temporary_directory(prefix='antibody-test') as dirname:
      # tbr_no_lgtm: review_url, request_timestamp, subject,
      # people_email_address, hash
      tbr_no_lgtm = (
          ('hello', '2015-07-13 11:11:11', 'pgervais@chromium.org',
           'git_hash_1', 'https://codereview.chromium.org/1175993003'),
          ('hello', '2015-07-13 11:11:11', 'hinoka@chromium.org',
           'git_hash_1', 'https://codereview.chromium.org/1175993003'),
          ('world', '2015-07-13 22:22:22', 'hinoka@chromium.org',
           'git_hash_2', 'https://codereview.chromium.org/1171763002'),
          ('world', '2015-07-13 22:22:22', 'keelerh@google.com',
           'git_hash_2', 'https://codereview.chromium.org/1171763002'),
      )
      antibody.get_tbr_by_user(tbr_no_lgtm, 
            'https://chromium.googlesource.com/infra/infra/+/', dirname)
      expected_out = {
        "by_user" : {
          "pgervais" : [['git_hash_1',
                         'https://codereview.chromium.org/1175993003',
                         '2015-07-13 11:11:11']],
          "hinoka" : [['git_hash_1',
                       'https://codereview.chromium.org/1175993003',
                       '2015-07-13 11:11:11'],
                      ['git_hash_2',
                       'https://codereview.chromium.org/1171763002',
                       '2015-07-13 22:22:22']],
          "keelerh" : [['git_hash_2',
                        'https://codereview.chromium.org/1171763002',
                        '2015-07-13 22:22:22']]
        },
        "gitiles_prefix" : "https://chromium.googlesource.com/infra/infra/+/",
      }
      with open(os.path.join(dirname, 'tbr_by_user.json'), 'r') as f:
        output = json.load(f)
      self.assertItemsEqual(output, expected_out)


  def test_get_gitiles_prefix(self):
    with infra_libs.temporary_directory(prefix='antibody-test') as dirname:
      with open(os.path.join(dirname, 'codereview.settings'), 'w') as f:
        f.writelines([
          'This file is used by gcl to get repository specific information.\n',
          'CODE_REVIEW_SERVER: https://codereview.chromium.org\n',
          'VIEW_VC: https://chromium.googlesource.com/infra/infra/+/\n',
          'CC_LIST: chromium-reviews@chromium.org\n',
          'PROJECT: infra\n',
        ])
      self.assertEqual(antibody.get_gitiles_prefix(dirname),
                       'https://chromium.googlesource.com/infra/infra/+/')

      with open(os.path.join(dirname, 'codereview.settings'), 'w') as f:
        f.writelines([
          'CC_LIST: chromium-reviews@chromium.org\n',
          'PROJECT: infra\n',
        ])
      self.assertEqual(antibody.get_gitiles_prefix(dirname), None)


  def test_get_project_name(self):
    with infra_libs.temporary_directory(prefix='antibody-test') as dirname:
      with open(os.path.join(dirname, 'codereview.settings'), 'w') as f:
        f.writelines([
          'This file is used by gcl to get repository specific information.\n',
          'CODE_REVIEW_SERVER: https://codereview.chromium.org\n',
          'VIEW_VC: https://chromium.googlesource.com/infra/infra/+/\n',
          'CC_LIST: chromium-reviews@chromium.org\n',
          'PROJECT: infra\n',
        ])
      self.assertEqual(antibody.get_project_name(dirname),
                       'infra')

      with open(os.path.join(dirname, 'codereview.settings'), 'w') as f:
        f.writelines([
          'CC_LIST: chromium-reviews@chromium.org\n',
          'VIEW_VC: https://chromium.googlesource.com/infra/infra/+/\n',
        ])
      self.assertEqual(antibody.get_project_name(dirname), None)