# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import webapp2

from handlers.flake import triage_flake_analysis
from handlers.flake.triage_flake_analysis import TriageFlakeAnalysis
from libs import analysis_status
from model import triage_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.test import wf_testcase


class TriageFlakeAnalysisTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [('/waterfall/triage_flake_analysis', TriageFlakeAnalysis)], debug=True)

  def testUpdateSuspectedFlakeAnalysisCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_flake_build_number = 100
    analysis.culprit = FlakeCulprit.Create('chromium', 'r1000', 1000, 'url',
                                           0.8)
    analysis.put()

    triage_flake_analysis._UpdateSuspectedFlakeAnalysis(
        analysis.key.urlsafe(), triage_status.TRIAGED_CORRECT, 'user')
    self.assertTrue(analysis.correct_culprit)

  @mock.patch.object(
      triage_flake_analysis.token, 'ValidateAuthToken', return_value=True)
  def testPostWithTriageResults(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_flake_build_number = 100
    analysis.put()

    self.mock_current_user(user_email='test@google.com', is_admin=False)

    response = self.test_app.post(
        '/waterfall/triage_flake_analysis',
        params={
            'key': analysis.key.urlsafe(),
            'triage_result': 1,
        })

    self.assertEqual(200, response.status_int)
    self.assertEqual({'success': True}, response.json_body)

  @mock.patch.object(
      triage_flake_analysis.token, 'ValidateAuthToken', return_value=True)
  def testPostMissingParameters(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_flake_build_number = 100
    analysis.put()

    self.mock_current_user(user_email='test@google.com', is_admin=False)

    response = self.test_app.post('/waterfall/triage_flake_analysis', params={})

    self.assertEqual(200, response.status_int)
    self.assertEqual({'success': False}, response.json_body)
