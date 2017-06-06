# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import pickle
import re

from google.appengine.ext import testbed
import webapp2
import webtest

from testing_utils import testing

from handlers import process_flake_analysis_request


class ProcessFlakeAnalysisRequestsTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/process-flake-analysis-request',
       process_flake_analysis_request.ProcessFlakeAnalysisRequest),
  ], debug=True)

  def testNonAdminCanNotSendRequest(self):
    self.test_app.post(
        '/process-flake-analysis-request?format=json', params='', status=401)

  @mock.patch.object(
      process_flake_analysis_request.flake_analysis_service,
      'ScheduleAnalysisForFlake')
  def testAdminCanRequestAnalysis(self, mocked_func):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    response = self.test_app.post(
        '/process-flake-analysis-request',
        params=pickle.dumps(('request', 'email', False)))
    self.assertEquals(200, response.status_int)
    mocked_func.assert_call_with(mock.call('request', 'email', False))
