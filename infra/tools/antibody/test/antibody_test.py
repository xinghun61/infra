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


def fake_extract_json_data(rietveld_url):
  url_components = re.split('(https?:\/\/)([\da-z\.-]+)', rietveld_url)
  with open('infra/tools/antibody/test/data/%s.txt' %url_components[3], 'r') \
       as f:
    return json.load(f)


class MyTest(auto_stub.TestCase):
  def test_arguments(self):
    parser = argparse.ArgumentParser()
    antibody.add_argparse_options(parser)
    args = parser.parse_args(['--rietveld-url', '1234'])
    self.assertEqual(args.rietveld_url, '1234')

    args = parser.parse_args(['-ru', '5678'])
    self.assertEqual(args.rietveld_url, '5678')

    args = parser.parse_args(['-ru', '90', '-f', 'abc'])
    self.assertEqual(args.filename, 'abc')


  def test_process_argparse_options(self):
    self.mock(code_review_parse, 'extract_json_data', 
              fake_extract_json_data)
    parser = argparse.ArgumentParser()
    antibody.add_argparse_options(parser)

    with infra_libs.temporary_directory(prefix='antibody-test') as dirname:
      file_name = os.path.join(dirname, 'rietveld_data.sqlite3')
      rietveld_url = 'https://codereview.chromium.org/1004453003'
      args = parser.parse_args(['-ru', rietveld_url, '-f', file_name])
      antibody.setup_rietveld_db(args.rietveld_url, args.filename)

      expected_table_headers = ('issue_num', 'lgtm', 'tbr', 'request_timestamp',
                                'rietveld_url')
      con = sqlite3.connect(file_name)
      with con:
        cur = con.cursor()
        cur.execute('pragma table_info(rietveld);')
        table_headers = cur.fetchall()
        for i in xrange(len(table_headers)):
          self.assertTrue(expected_table_headers[i] == table_headers[i][1])
