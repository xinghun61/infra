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

from common import chrome_dependency_fetcher
from crash import crash_pipeline
from crash.crash_pipeline import CrashWrapperPipeline
from crash.findit import Findit
from crash.findit_for_chromecrash import FinditForFracas
from crash.test.predator_testcase import PredatorTestCase
from crash.type_enums import CrashClient
from handlers.crash import crash_handler
from libs.gitiles import gitiles_repository
from model import analysis_status
from model.crash.crash_analysis import CrashAnalysis
from model.crash.crash_config import CrashConfig


class CrashHandlerTest(PredatorTestCase):
  app_module = webapp2.WSGIApplication([
      ('/_ah/push-handlers/crash/fracas', crash_handler.CrashHandler),
  ], debug=True)

  def testDoNotScheduleNewAnalysisIfNeedsNewAnalysisReturnsFalse(self):
    mock_findit = self.GetMockFindit()
    self.mock(mock_findit, 'NeedsNewAnalysis', lambda _: False)
    self.mock(crash_pipeline, 'FinditForClientID', lambda *_: mock_findit)
    # Check policy failed due to empty client config.
    self.assertFalse(crash_handler.ScheduleNewAnalysis(
        self.GetDummyChromeCrashData()))

  def testScheduleNewAnalysisIfNeedsNewAnalysisReturnsTrue(self):
    mock_findit = self.GetMockFindit(client_id=CrashClient.FRACAS)
    self.mock(mock_findit, 'NeedsNewAnalysis', lambda _: True)
    self.mock(crash_pipeline, 'FinditForClientID', lambda *_: mock_findit)
    self.assertTrue(crash_handler.ScheduleNewAnalysis(
        self.GetDummyChromeCrashData(client_id=CrashClient.FRACAS)))

  def testHandlePostScheduleNewAnalysis(self):
    chrome_version = '50.2500.0.0'
    signature = 'signature/here'
    channel = 'canary'
    platform = 'mac'
    crash_data = self.GetDummyChromeCrashData(
        client_id=CrashClient.FRACAS,
        channel=channel, platform=platform,
        signature=signature, version=chrome_version,
        process_type='renderer')

    request_json_data = {
        'message': {
            'data': base64.b64encode(json.dumps(crash_data)),
            'message_id': 'id',
        },
        'subscription': 'subscription',
    }

    self.MockPipeline(
        CrashWrapperPipeline, True,
        (crash_data['client_id'], crash_data['crash_identifiers']))
    self.mock(CrashAnalysis, 'Initialize', lambda *_: None)

    self.test_app.post_json('/_ah/push-handlers/crash/fracas',
                            request_json_data)
