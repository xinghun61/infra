# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import copy
import json
import logging
import mock

from google.appengine.api import app_identity
from google.appengine.ext import ndb
import webapp2
from webtest.app import AppError

from analysis.type_enums import CrashClient
from common import crash_pipeline
from common.appengine_testcase import AppengineTestCase
from common.crash_pipeline import CrashAnalysisPipeline
from common.crash_pipeline import CrashWrapperPipeline
from common.crash_pipeline import PublishResultPipeline
from common.predator_app import PredatorApp
from common.predator_for_chromecrash import PredatorForFracas
from common.model.crash_analysis import CrashAnalysis
from common.model.crash_config import CrashConfig
from frontend.handlers import crash_handler
from libs import analysis_status
from libs.gitiles import gitiles_repository


class CrashHandlerTest(AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/_ah/push-handlers/crash/fracas', crash_handler.CrashHandler),
      ('/_ah/push-handlers/crash/clusterfuzz', crash_handler.CrashHandler),
  ], debug=True)

  @mock.patch('common.crash_pipeline.CrashWrapperPipeline.start')
  def testStartAnalysis(self, mock_start):
    json_crash_data = self.GetDummyClusterfuzzData()
    self.MockPipeline(CrashWrapperPipeline, None, json_crash_data)
    mock_start.return_value = None
    with mock.patch(
        'common.crash_pipeline.PredatorForClientID') as mock_predator:
      mock_predator.return_value = self.GetMockPredatorApp()
      crash_handler.StartAnalysis(json_crash_data)

  @mock.patch('common.crash_pipeline.CrashWrapperPipeline.start')
  @mock.patch('common.model.crash_analysis.CrashAnalysis.Initialize')
  def testHandlePostStartAnalysis(self, initialize, mock_start):
    initialize.return_value = None
    json_crash_data = self.GetDummyClusterfuzzData(redo=True)

    mock_predator_app = self.GetMockPredatorApp()
    mock_predator_app.NeedsNewAnalysis = mock.Mock(return_value=True)
    with mock.patch('common.crash_pipeline.PredatorForClientID') as (
        mock_predator_app_for_client):

      mock_predator_app_for_client.return_value = mock_predator_app
      request_json_data = {
          'message': {
              'data': base64.b64encode(json.dumps(json_crash_data)),
              'message_id': 'id',
          },
          'subscription': 'subscription',
      }
      self.MockPipeline(CrashWrapperPipeline, None, [json_crash_data])

      self.test_app.post_json('/_ah/push-handlers/crash/clusterfuzz',
                              request_json_data)
      self.assertTrue(mock_start.called)
