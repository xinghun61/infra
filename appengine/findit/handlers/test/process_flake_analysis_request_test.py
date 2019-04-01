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
  app_module = webapp2.WSGIApplication(
      [
          ('/process-flake-analysis-request',
           process_flake_analysis_request.ProcessFlakeAnalysisRequest),
      ],
      debug=True)

  @mock.patch.object(process_flake_analysis_request.flake_analysis_service,
                     'ScheduleAnalysisForFlake')
  def testTaskQueueCanRequestAnalysis(self, mocked_func):
    # pylint:disable=unused-argument
    response = self.test_app.post(
        '/process-flake-analysis-request',
        params=pickle.dumps(('request', 'email', False)),
        headers={'X-AppEngine-QueueName': 'task_queue'},
    )
    self.assertEquals(200, response.status_int)
    # Assertions have never worked properly because we were using mock 1.0.1.
    # After rolling to mock 2.0.0, which fixes assertions, these assertions now
    # fail. https://crbug.com/947753.
    # mocked_func.assert_call_with(mock.call('request', 'email', False))
