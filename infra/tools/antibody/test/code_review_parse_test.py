# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import StringIO
import unittest

from infra.tools.antibody import code_review_parse


def fake_extract_json_data(issue_num):
  return json.load(open("infra/tools/antibody/test/data/%s.txt"
                        %str(issue_num), "r"))


class TestCodeReviewParse(unittest.TestCase):
  lgtm_no_tbr = 1158153006
  not_lgtm_no_tbr = 1175993003
  mult_lgtm_no_tbr = 1146053009
  no_lgtm_tbr = 1004453003
  no_lgtm_mult_tbr = 1171763002
  lgtm_tbr = 1175623002


  def testContainsLGTM(self):
    issues_with_lgtm = (self.lgtm_no_tbr, self.mult_lgtm_no_tbr, self.lgtm_tbr)
    for issue in issues_with_lgtm:
      self.assertTrue(code_review_parse.contains_lgtm(
                                            fake_extract_json_data(issue)))

    issues_without_lgtm = (self.not_lgtm_no_tbr, self.no_lgtm_tbr,
                           self.no_lgtm_mult_tbr)
    for issue in issues_without_lgtm:
      self.assertFalse(code_review_parse.contains_lgtm(
                                            fake_extract_json_data(issue)))
 

  def testContainsTBR(self):
    issues_with_tbr = (self.no_lgtm_tbr, self.no_lgtm_mult_tbr, self.lgtm_tbr)
    for issue in issues_with_tbr:
      self.assertTrue(code_review_parse.contains_tbr(
                                            fake_extract_json_data(issue)))

    issues_without_tbr = (self.lgtm_no_tbr, self.not_lgtm_no_tbr, 
                          self.mult_lgtm_no_tbr)
    for issue in issues_without_tbr:
      self.assertFalse(code_review_parse.contains_tbr(
                                            fake_extract_json_data(issue)))
