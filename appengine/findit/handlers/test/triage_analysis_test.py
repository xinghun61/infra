# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from google.appengine.ext import testbed
import webapp2

from testing_utils import testing

from handlers import triage_analysis
from model.wf_analysis import WfAnalysis
from model import wf_analysis_result_status
from model import wf_analysis_status
from waterfall import buildbot


class TriageAnalysisTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/triage-analysis', triage_analysis.TriageAnalysis),
  ], debug=True)

  def setUp(self):
    super(TriageAnalysisTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number_incomplete = 120  # Analysis is not completed yet.
    self.build_number_found = 122  # Suspected CLs are found for this build.
    self.build_number_not_found = 123  # No suspected CLs found.
    self.suspected_cls = [{
        'repo_name': 'chromium',
        'revision': 'r1',
        'commit_position': 123,
        'url': 'https://codereview.chromium.org/123',
    }]

    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_incomplete)
    analysis.status = wf_analysis_status.ANALYZING
    analysis.put()

    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_found)
    analysis.status = wf_analysis_status.ANALYZED
    analysis.suspected_cls = self.suspected_cls
    analysis.put()

    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_not_found)
    analysis.status = wf_analysis_status.ANALYZED
    analysis.put()

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

  def testUpdateAnalysisResultStatusWhenAnalysisIsIncomplete(self):
    success = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_incomplete, True)
    self.assertFalse(success)
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_found)
    self.assertIsNone(analysis.result_status)

  def testUpdateAnalysisResultStatusWhenFoundAndCorrect(self):
    success = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_found, True)
    self.assertTrue(success)
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_found)
    self.assertEquals(wf_analysis_result_status.FOUND_CORRECT,
                      analysis.result_status)
    self.assertEquals(self.suspected_cls, analysis.culprit_cls)

  def testUpdateAnalysisResultStatusWhenFoundButIncorrect(self):
    success = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_found, False)
    self.assertTrue(success)
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_found)
    self.assertEquals(wf_analysis_result_status.FOUND_INCORRECT,
                      analysis.result_status)
    self.assertIsNone(analysis.culprit_cls)

  def testUpdateAnalysisResultStatusWhenNotFoundAndCorrect(self):
    success = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_not_found, True)
    self.assertTrue(success)
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_not_found)
    self.assertEquals(wf_analysis_result_status.NOT_FOUND_CORRECT,
                      analysis.result_status)
    self.assertIsNone(analysis.culprit_cls)

  def testUpdateAnalysisResultStatusWhenNotFoundButIncorrect(self):
    success = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_not_found, False)
    self.assertTrue(success)
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_not_found)
    self.assertEquals(wf_analysis_result_status.NOT_FOUND_INCORRECT,
                      analysis.result_status)
    self.assertIsNone(analysis.culprit_cls)

  def testInvalidBuildUrl(self):
    build_url = 'http://invalid/build/url'
    response = self.test_app.get(
        '/triage-analysis',
        params={'url': build_url, 'correct': True, 'format': 'json'})
    self.assertEquals(200, response.status_int)
    self.assertEquals({'success': False}, response.json_body)

  def testSuccessfulTriage(self):
    build_url = buildbot.CreateBuildUrl(
        self.master_name, self.builder_name, self.build_number_found)
    response = self.test_app.get(
        '/triage-analysis',
        params={'url': build_url, 'correct': True, 'format': 'json'})
    self.assertEquals(200, response.status_int)
    self.assertEquals({'success': True}, response.json_body)
