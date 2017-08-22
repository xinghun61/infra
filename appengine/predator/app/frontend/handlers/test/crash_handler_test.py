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
from common.crash_pipeline import CrashWrapperPipeline
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

  def testNeedNewAnalysisIfIsARedo(self):
    mock_predator_app = self.GetMockPredatorApp()
    with mock.patch('common.crash_pipeline.PredatorForClientID') as mock_func:
      mock_func.return_value = mock_predator_app
      need_new_analysis, _ = crash_handler.NeedNewAnalysis(
          self.GetDummyClusterfuzzData(redo=True))

      self.assertTrue(need_new_analysis)

  @mock.patch('common.crash_pipeline.PredatorForClientID')
  def testDoNotNeedNewAnalysisIfNeedsNewAnalysisReturnsFalse(
      self, mock_predator_app_for_client_ID):
    mock_predator_app = self.GetMockPredatorApp()
    mock_predator_app.NeedsNewAnalysis = mock.Mock(return_value=False)
    mock_predator_app_for_client_ID.return_value = mock_predator_app

    need_new_analysis, _ = crash_handler.NeedNewAnalysis(
        self.GetDummyChromeCrashData())

    # Check policy failed due to empty client config.
    self.assertFalse(need_new_analysis)

  @mock.patch('common.crash_pipeline.PredatorForClientID')
  def testNeedNewAnalysisIfNeedsNewAnalysisReturnsTrue(
      self, mock_predator_app_for_client_ID):
    mock_predator_app = self.GetMockPredatorApp(client_id=CrashClient.FRACAS)
    mock_predator_app.NeedsNewAnalysis = mock.Mock(return_value=True)
    mock_predator_app_for_client_ID.return_value = mock_predator_app
    self.assertTrue(crash_handler.NeedNewAnalysis(
        self.GetDummyChromeCrashData(client_id=CrashClient.FRACAS)))

  @mock.patch('common.crash_pipeline.CrashWrapperPipeline.start')
  def testStartNewAnalysis(self, mock_start):
    client_id = 'clusterfuzz'
    crash_identifiers = {'testcase': 1324345}
    self.MockPipeline(CrashWrapperPipeline, None,
                      (client_id, crash_identifiers))
    mock_start.return_value = None
    crash_handler.StartNewAnalysis(client_id, crash_identifiers)

  @mock.patch('common.predator_app.PredatorApp._CheckPolicy')
  def testHandlePostDoesNotStartNewAnalysis(self, mock_check_policy):
    mock_check_policy.return_value = False
    json_crash_data = self.GetDummyClusterfuzzData()
    mock_predator_app = self.GetMockPredatorApp()
    with mock.patch('common.crash_pipeline.PredatorForClientID') as mock_func:
      mock_func.return_value = mock_predator_app
      need_new_analysis, _ = crash_handler.NeedNewAnalysis(
          json_crash_data)
      self.assertFalse(need_new_analysis)

      request_json_data = {
          'message': {
              'data': base64.b64encode(json.dumps(json_crash_data)),
              'message_id': 'id',
          },
          'subscription': 'subscription',
      }
      self.test_app.post_json('/_ah/push-handlers/crash/fracas',
                              request_json_data)

  @mock.patch('common.model.crash_analysis.CrashAnalysis.Initialize')
  def testHandlePostStartNewAnalysis(self, initialize):
    initialize.return_value = None
    json_crash_data = self.GetDummyClusterfuzzData(redo=True)

    mock_predator_app = self.GetMockPredatorApp()
    with mock.patch('common.crash_pipeline.PredatorForClientID') as (
        mock_predator_app_for_client):

      mock_predator_app_for_client.return_value = mock_predator_app
      _, crash_data = crash_handler.NeedNewAnalysis(json_crash_data)

      request_json_data = {
          'message': {
              'data': base64.b64encode(json.dumps(json_crash_data)),
              'message_id': 'id',
          },
          'subscription': 'subscription',
      }
      self.MockPipeline(
          CrashWrapperPipeline, None,
          (json_crash_data['client_id'], crash_data.identifiers))

      self.test_app.post_json('/_ah/push-handlers/crash/clusterfuzz',
                              request_json_data)
