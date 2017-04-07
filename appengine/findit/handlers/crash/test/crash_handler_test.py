# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import copy
import json
import logging

from google.appengine.api import app_identity
from google.appengine.ext import ndb
import webapp2
from webtest.app import AppError

from crash import crash_pipeline
from crash.crash_pipeline import CrashWrapperPipeline
from crash.findit import Findit
from crash.findit_for_chromecrash import FinditForFracas
from crash.test.predator_testcase import PredatorTestCase
from crash.type_enums import CrashClient
from handlers.crash import crash_handler
from libs import analysis_status
from libs.gitiles import gitiles_repository
from model.crash.crash_analysis import CrashAnalysis
from model.crash.crash_config import CrashConfig


class CrashHandlerTest(PredatorTestCase):
  app_module = webapp2.WSGIApplication([
      ('/_ah/push-handlers/crash/fracas', crash_handler.CrashHandler),
  ], debug=True)

  def testNeedNewAnalysisIfIsARedo(self):
    self.assertTrue(crash_handler.NeedNewAnalysis(
        self.GetDummyClusterfuzzData(redo=True)))

  def testDoNotNeedNewAnalysisIfNeedsNewAnalysisReturnsFalse(self):
    mock_findit = self.GetMockFindit()
    self.mock(mock_findit, 'NeedsNewAnalysis', lambda _: False)
    self.mock(crash_pipeline, 'FinditForClientID', lambda *_: mock_findit)
    # Check policy failed due to empty client config.
    self.assertFalse(crash_handler.NeedNewAnalysis(
        self.GetDummyChromeCrashData()))

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

  def testHandlePostDoesNotStartNewAnalysis(self):
    crash_data = self.GetDummyClusterfuzzData(redo=True)
    self.assertTrue(crash_handler.NeedNewAnalysis(crash_data))

    request_json_data = {
        'message': {
            'data': base64.b64encode(json.dumps(crash_data)),
            'message_id': 'id',
        },
        'subscription': 'subscription',
    }

    self.mock(crash_handler, 'NeedNewAnalysis', lambda *_: False)
    self.test_app.post_json('/_ah/push-handlers/crash/fracas',
                            request_json_data)

  def testHandlePostStartNewAnalysis(self):
    crash_data = self.GetDummyClusterfuzzData(redo=True)
    self.assertTrue(crash_handler.NeedNewAnalysis(crash_data))

    request_json_data = {
        'message': {
            'data': base64.b64encode(json.dumps(crash_data)),
            'message_id': 'id',
        },
        'subscription': 'subscription',
    }

    self.MockPipeline(
        CrashWrapperPipeline, None,
        (crash_data['client_id'], crash_data['crash_identifiers']))

    self.test_app.post_json('/_ah/push-handlers/crash/fracas',
                            request_json_data)
