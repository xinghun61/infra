# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import re
import sqlite3
import unittest

import infra_libs
from infra.tools.antibody import code_review_parse


def fake_extract_json_data(rietveld_url):
  url_components = re.split('(https?:\/\/)([\da-z\.-]+)', rietveld_url)
  return json.load(open('infra/tools/antibody/test/data%s.txt'
                        %url_components[3], 'r'))


class TestCodeReviewParse(unittest.TestCase):
  lgtm_no_tbr = 'https://codereview.chromium.org/1158153006'
  not_lgtm_no_tbr = 'https://codereview.chromium.org/1175993003'
  mult_lgtm_no_tbr = 'https://codereview.chromium.org/1146053009'
  no_lgtm_tbr = 'https://codereview.chromium.org/1004453003'
  no_lgtm_mult_tbr = 'https://codereview.chromium.org/1171763002'
  lgtm_tbr = 'https://codereview.chromium.org/1175623002'

  lgtm_no_tbr_num = 1158153006
  not_lgtm_no_tbr_num = 1175993003
  mult_lgtm_no_tbr_num = 1146053009
  no_lgtm_tbr_num = 1004453003
  no_lgtm_mult_tbr_num = 1171763002
  lgtm_tbr_num = 1175623002


  def test_contains_lgtm(self):
    issues_with_lgtm = (self.lgtm_no_tbr, self.mult_lgtm_no_tbr, self.lgtm_tbr)
    for issue in issues_with_lgtm:
      self.assertTrue(code_review_parse.contains_lgtm(
                                            fake_extract_json_data(issue)))

    issues_without_lgtm = (self.not_lgtm_no_tbr, self.no_lgtm_tbr,
                           self.no_lgtm_mult_tbr)
    for issue in issues_without_lgtm:
      self.assertFalse(code_review_parse.contains_lgtm(
                                            fake_extract_json_data(issue)))
 

  def test_contains_tbr(self):
    issues_with_tbr = (self.no_lgtm_tbr, self.no_lgtm_mult_tbr, self.lgtm_tbr)
    for issue in issues_with_tbr:
      self.assertTrue(code_review_parse.contains_tbr(
                                            fake_extract_json_data(issue)))

    issues_without_tbr = (self.lgtm_no_tbr, self.not_lgtm_no_tbr, 
                          self.mult_lgtm_no_tbr)
    for issue in issues_without_tbr:
      self.assertFalse(code_review_parse.contains_tbr(
                                            fake_extract_json_data(issue)))


  def test_to_canonical_rietveld_url(self):
    chrome_internal_url = 'https://chromereviews.googleplex.com/210457013/'
    self.assertEqual(chrome_internal_url,
          code_review_parse.to_canonical_rietveld_url(chrome_internal_url))
    
    cr_appspot_url = 'https://codereview.appspot.com/244460044/'
    self.assertEqual(cr_appspot_url,
                    code_review_parse.to_canonical_rietveld_url(cr_appspot_url))

    chromiumcr_url = 'https://chromiumcodereview.appspot.com/1147143006/'
    self.assertEqual('https://codereview.chromium.org/1147143006/',
                    code_review_parse.to_canonical_rietveld_url(chromiumcr_url))

    chromiumcr_hr_url = 'https://chromiumcodereview-hr.appspot.com/1147143006/'
    self.assertEqual('https://codereview.chromium.org/1147143006/',
                 code_review_parse.to_canonical_rietveld_url(chromiumcr_hr_url))

    codereview_chromium_url = 'https://codereview.chromium.org/1147143006/'
    self.assertEqual(codereview_chromium_url,
           code_review_parse.to_canonical_rietveld_url(codereview_chromium_url))


  def test_write_data_to_db(self):
    with infra_libs.temporary_directory(prefix='antibody-test') as dirname:
      file_name = os.path.join(dirname, 'rietveld_data.sqlite3')
      con = sqlite3.connect(file_name)
      with con:
        cur = con.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS rietveld (issue_num, ' + \
                    'lgtm, tbr, request_timestamp, rietveld_url PRIMARY KEY)')
        issues = (self.lgtm_no_tbr, self.not_lgtm_no_tbr, self.mult_lgtm_no_tbr,
                  self.no_lgtm_tbr, self.no_lgtm_mult_tbr, self.lgtm_tbr)
        for issue in issues:
          code_review_parse.write_data_to_db(issue, 
                                       fake_extract_json_data(issue), file_name)
    
        # format: issue_num, lgtm, tbr, time (not tested)
        expected_out = (
            (self.lgtm_no_tbr_num, 1, 0, self.lgtm_no_tbr),
            (self.not_lgtm_no_tbr_num, 0, 0, self.not_lgtm_no_tbr),
            (self.mult_lgtm_no_tbr_num, 1, 0, self.mult_lgtm_no_tbr),
            (self.no_lgtm_tbr_num, 0, 1, self.no_lgtm_tbr),
            (self.no_lgtm_mult_tbr_num, 0, 1, self.no_lgtm_mult_tbr),
            (self.lgtm_tbr_num, 1, 1, self.lgtm_tbr),
        )
        cur.execute('SELECT * FROM rietveld;')
        db_data = cur.fetchall()
        for i in xrange(len(db_data)):
          self.assertEqual(db_data[i][:3], expected_out[i][:3])
          self.assertEqual(db_data[i][-1], expected_out[i][-1])
