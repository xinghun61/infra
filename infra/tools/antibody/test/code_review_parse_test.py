# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import re
import sqlite3
import unittest

import infra_libs
import infra.tools.antibody.cloudsql_connect as csql
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
  lgtm_not_lgtm_no_tbr = 'https://codereview.chromium.org/1177013002'

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


  def test_get_rietveld_data_for_review_people(self):
    # email_address, review_url, timestamp, request_timestamp, type
    expected_out = (
        ('chromium-reviews@chromium.org', self.lgtm_not_lgtm_no_tbr,
         '2015-06-10 22:00:02', None, 'cc'),
        ('ksho@google.com', self.lgtm_not_lgtm_no_tbr,
         '2015-06-10 22:00:02', None, 'owner'),
        ('pgervais@chromium.org', self.lgtm_not_lgtm_no_tbr,
         '2015-06-10 22:00:02', None, 'reviewer'),
        ('hinoka@chromium.org', self.lgtm_not_lgtm_no_tbr,
         '2015-06-10 22:00:02', None, 'reviewer'),
        ('pgervais@chromium.org', self.lgtm_not_lgtm_no_tbr,
         '2015-06-10 22:41:29', None, 'lgtm'),
        ('pgervais@chromium.org', self.lgtm_not_lgtm_no_tbr,
         '2015-06-10 22:43:06', None, 'not lgtm'),
        ('pgervais@chromium.org', self.lgtm_not_lgtm_no_tbr,
         '2015-06-11 18:39:50', None, 'lgtm'),
    )
    db_data_all = code_review_parse.get_rietveld_data_for_review_people(
        self.lgtm_not_lgtm_no_tbr)
    db_comparable = [(x[0], x[1], x[2], None, x[4]) for x in db_data_all]
    self.assertEqual(set(db_comparable), set(expected_out))


  def test_get_rietveld_data_for_review(self):
    # review_url, request_timestamp, committed_timestamp, patchset_still_exists
    # reverted, project_prj_id
    expected_out = (self.lgtm_no_tbr, None, '2015-06-02 16:46:42', True,
                    None, None)
    out = code_review_parse.get_rietveld_data_for_review(self.lgtm_no_tbr)
    out_comparable = (out[0], None) + out[2:]
    self.assertEqual(out_comparable, expected_out)
