# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import os
import re

import webapp2
import webtest

from crash import crash_pipeline
from crash.test.crash_testcase import CrashTestCase
from handlers.crash import crash_handler


class CrashHandlerTest(CrashTestCase):
  app_module = webapp2.WSGIApplication([
      ('/_ah/push-handlers/crash/fracas', crash_handler.CrashHandler),
  ], debug=True)

  def _MockScheduleNewAnalysisForCrash(self, requested_crashes):
    def Mocked_ScheduleNewAnalysisForCrash(*crash_data, **_):
      requested_crashes.append(crash_data)
    self.mock(crash_pipeline, 'ScheduleNewAnalysisForCrash',
              Mocked_ScheduleNewAnalysisForCrash)

  def testAnalysisScheduled(self):
    requested_crashes = []
    self._MockScheduleNewAnalysisForCrash(requested_crashes)
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    client_id = 'fracas'
    channel = 'supported_channel'
    platform = 'supported_platform'
    signature = 'signature/here'
    stack_trace = 'frame1\nframe2\nframe3'
    chrome_version = '50.2500.0.0'
    historic_metadata = [{'chrome_version': '50.2500.0.0', 'cpm': 0.6}]

    crash_identifiers = {
        'chrome_version': chrome_version,
        'signature': signature,
        'channel': channel,
        'platform': platform,
        'process_type': 'renderer'
    }

    request_json_data = {
        'message': {
            'data': base64.b64encode(json.dumps({
                'customized_data': {
                    'channel': 'supported_channel',
                    'historical_metadata': [
                        {
                            'chrome_version': '50.2500.0.0',
                            'cpm': 0.6
                        },
                    ]
                },
                'chrome_version': '50.2500.0.0',
                'signature': 'signature/here',
                'client_id': 'fracas',
                'platform': 'supported_platform',
                'crash_identifiers': {
                    'chrome_version': '50.2500.0.0',
                    'signature': 'signature/here',
                    'channel': 'supported_channel',
                    'platform': 'supported_platform',
                    'process_type': 'renderer'
                },
                'stack_trace': 'frame1\nframe2\nframe3'
            })),
            'message_id': 'id',
        },
        'subscription': 'subscription',
    }

    self.test_app.post_json('/_ah/push-handlers/crash/fracas',
                            request_json_data)

    self.assertEqual(1, len(requested_crashes))
    self.assertEqual(
        (crash_identifiers, chrome_version, signature, client_id,
         platform, stack_trace, {'channel': channel,
                                 'historical_metadata': historic_metadata}),
        requested_crashes[0])
