# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool-specific testable functions for antibody."""

import argparse
import json
import os
import re
import sqlite3

import infra_libs
from testing_support import auto_stub
from infra.tools.antibody import code_review_parse
from infra.tools.antibody import antibody

THIS_DIR = os.path.dirname(os.path.realpath(__file__))


class MyTest(auto_stub.TestCase):
  def test_arguments(self):
    parser = argparse.ArgumentParser()
    antibody.add_argparse_options(parser)
    args = parser.parse_args(['--rietveld-url', '1234', '-p', '3'])
    self.assertEqual(args.rietveld_url, '1234')
    self.assertEqual(args.sql_password_file, '3')

    args = parser.parse_args(['-r', '5678', '-p', '4'])
    self.assertEqual(args.rietveld_url, '5678')
    self.assertEqual(args.sql_password_file, '4')
  

  def test_generate_antibody_ui(self):
    with infra_libs.temporary_directory(prefix='antibody-test') as dirname:
      file_name = os.path.join(dirname, 'fake_ui.html')
      commit_data = 'data/sample_suspicious_commits.txt'
      with open(os.path.join(THIS_DIR, commit_data), 'r') as f:
        suspicious_commits_data = [line.rstrip('\n').split(',') for line in f]
      temp_data_gitiles="https://chromium.googlesource.com/infra/infra/+/"
      antibody.generate_antibody_ui(suspicious_commits_data, temp_data_gitiles,
                                    file_name)
      with open(file_name, 'r') as f:
        file_string = f.read()
        self.assertTrue(file_string)
        self.assertFalse('{{' in file_string)
        self.assertFalse('}}' in file_string)
