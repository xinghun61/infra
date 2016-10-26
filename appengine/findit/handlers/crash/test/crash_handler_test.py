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
from crash.findit import Findit
from crash.test.crash_testcase import CrashTestCase
from handlers.crash import crash_handler


class CrashHandlerTest(CrashTestCase):
  app_module = webapp2.WSGIApplication([
      ('/_ah/push-handlers/crash/fracas', crash_handler.CrashHandler),
  ], debug=True)

  def testAnalysisScheduled(self):
    # We need to mock out the method on Findit itself (rather than using a
    # subclass), since this method only gets called on objects we
    # ourselves don't construct.
    requested_crashes = []
    def _MockScheduleNewAnalysis(_self, crash_data, **_):
      requested_crashes.append(crash_data)
    self.mock(Findit, 'ScheduleNewAnalysis', _MockScheduleNewAnalysis)

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    channel = 'supported_channel'
    platform = 'supported_platform'
    signature = 'signature/here'
    chrome_version = '50.2500.0.0'
    crash_data = {
        'client_id': 'fracas',
        'platform': platform,
        'signature': signature,
        'stack_trace': 'frame1\nframe2\nframe3',
        'chrome_version': chrome_version,
        'crash_identifiers': {
            'chrome_version': chrome_version,
            'signature': signature,
            'channel': channel,
            'platform': platform,
            'process_type': 'renderer',
        },
        'customized_data': {
            'channel': channel,
            'historical_metadata':
                [{'chrome_version': chrome_version, 'cpm': 0.6}],
        },
    }

    request_json_data = {
        'message': {
            'data': base64.b64encode(json.dumps(crash_data)),
            'message_id': 'id',
        },
        'subscription': 'subscription',
    }

    self.test_app.post_json('/_ah/push-handlers/crash/fracas',
                            request_json_data)

    self.assertEqual(1, len(requested_crashes))
    self.assertEqual(crash_data, requested_crashes[0])
