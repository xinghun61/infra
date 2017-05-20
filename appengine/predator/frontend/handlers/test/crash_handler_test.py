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
from common.findit import Findit
from common.findit_for_chromecrash import FinditForFracas
from common.model.crash_analysis import CrashAnalysis
from common.model.crash_config import CrashConfig
from frontend.handlers import crash_handler
from libs import analysis_status
from libs.gitiles import gitiles_repository


class CrashHandlerTest(AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/_ah/push-handlers/crash/fracas', crash_handler.CrashHandler),
  ], debug=True)

  def testNeedNewAnalysisIfIsARedo(self):
    mock_findit = self.GetMockFindit()
    with mock.patch('common.crash_pipeline.FinditForClientID') as mock_func:
      mock_func.return_value = mock_findit
      need_new_analysis, _ = crash_handler.NeedNewAnalysis(
          self.GetDummyClusterfuzzData(redo=True))

      self.assertTrue(need_new_analysis)

  def testDoNotNeedNewAnalysisIfNeedsNewAnalysisReturnsFalse(self):
    mock_findit = self.GetMockFindit()
    self.mock(mock_findit, 'NeedsNewAnalysis', lambda _: False)
    self.mock(crash_pipeline, 'FinditForClientID', lambda *_: mock_findit)
    need_new_analysis, _ = crash_handler.NeedNewAnalysis(
        self.GetDummyChromeCrashData())
    # Check policy failed due to empty client config.
    self.assertFalse(need_new_analysis)

  def testNeedNewAnalysisIfNeedsNewAnalysisReturnsTrue(self):
    mock_findit = self.GetMockFindit(client_id=CrashClient.FRACAS)
    self.mock(mock_findit, 'NeedsNewAnalysis', lambda _: True)
    self.mock(crash_pipeline, 'FinditForClientID', lambda *_: mock_findit)
    self.assertTrue(crash_handler.NeedNewAnalysis(
        self.GetDummyChromeCrashData(client_id=CrashClient.FRACAS)))

  def testStartNewAnalysis(self):
    client_id = 'clusterfuzz'
    crash_identifiers = {'testcase': 1324345}
    self.MockPipeline(CrashWrapperPipeline, None,
                      (client_id, crash_identifiers))
    self.mock(CrashWrapperPipeline, 'start', lambda *args, **kwargs: None)
    crash_handler.StartNewAnalysis(client_id, crash_identifiers)

  @mock.patch('common.findit.Findit._CheckPolicy')
  def testHandlePostDoesNotStartNewAnalysis(self, mock_check_policy):
    mock_check_policy.return_value = False
    json_crash_data = self.GetDummyClusterfuzzData()
    mock_findit = self.GetMockFindit()
    with mock.patch('common.crash_pipeline.FinditForClientID') as mock_func:
      mock_func.return_value = mock_findit
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

  def testHandlePostStartNewAnalysis(self):
    json_crash_data = self.GetDummyClusterfuzzData(redo=True)

    mock_findit = self.GetMockFindit()
    with mock.patch(
        'common.crash_pipeline.FinditForClientID') as mock_findit_for_client:

      mock_findit_for_client.return_value = mock_findit
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

      self.test_app.post_json('/_ah/push-handlers/crash/fracas',
                              request_json_data)
