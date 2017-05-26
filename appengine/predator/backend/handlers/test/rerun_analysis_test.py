# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock
import webapp2

from google.appengine.api import users

from analysis.type_enums import CrashClient
from backend.handlers.rerun_analysis import RerunAnalysis
from common.crash_pipeline import RerunPipeline
from gae_libs.pipeline_wrapper import pipeline_handlers
from gae_libs.testcase import TestCase


class RerunAnalysisTest(TestCase):
  """Tests utility functions and ``RerunAnalysis`` handler."""
  app_module = webapp2.WSGIApplication([
      ('/process/rerun-analysis', RerunAnalysis),
  ], debug=True)

  @mock.patch('libs.time_util.GetUTCNow')
  @mock.patch('common.crash_pipeline.RerunPipeline.start')
  def testHandleGet(self, mock_run, mock_utcnow):
    mock_utcnow.return_value = datetime(2017, 5, 20, 0, 0, 0)
    mock_run.return_value = None
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    response = self.test_app.get(
        '/process/rerun-analysis?start_date=2017-05-19&end_date=2017-05-20')
    self.assertEqual(response.status_int, 200)
