# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import os
import re

import webapp2
import webtest

from crash.test.crash_testcase import CrashTestCase
from handlers.crash import fracas_crash
from model.crash.crash_config import CrashConfig


class FracasCrashTest(CrashTestCase):
  app_module = webapp2.WSGIApplication([
      ('/crash/fracas', fracas_crash.FracasCrash),
  ], debug=True)

  def _MockScheduleNewAnalysisForCrash(self, requested_crashes):
    def Mocked_ScheduleNewAnalysisForCrash(*crash_data, **_):
      requested_crashes.append(crash_data)
    self.mock(fracas_crash.fracas_crash_pipeline, 'ScheduleNewAnalysisForCrash',
              Mocked_ScheduleNewAnalysisForCrash)

  def testUnauthorizedToken(self):
    requested_crashes = []
    self._MockScheduleNewAnalysisForCrash(requested_crashes)
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*403.* Unauthorized access: invalid token.*',
                   re.MULTILINE | re.DOTALL),
        self.test_app.post, '/crash/fracas?token=UnauthorizedToken')
    self.assertEqual(0, len(requested_crashes))

  def testAnalysisScheduled(self):
    requested_crashes = []
    self._MockScheduleNewAnalysisForCrash(requested_crashes)

    channel = 'supported_channel'
    platform = 'supported_platform'
    signature = 'signature/here'
    stack_trace = 'frame1\nframe2\nframe3'
    chrome_version = '50.2500.0.0'
    versions_to_cpm = [['50.2500.0.0']]

    request_json_data = {
        'message': {
            'data': base64.b64encode(json.dumps({
                'channel': channel,
                'platform': platform,
                'signature': signature,
                'stack_trace': stack_trace,
                'chrome_version': chrome_version,
                'versions_to_cpm': versions_to_cpm,
            })),
            'message_id': 'id',
        },
        'subscription': 'subscription',
    }

    crash_config = CrashConfig.Get()
    token = crash_config.fracas.get('crash_data_push_token')
    self.test_app.post_json('/crash/fracas?token=%s' % token, request_json_data)

    self.assertEqual(1, len(requested_crashes))
    self.assertEqual(
        (channel, platform, signature, stack_trace,
         chrome_version, versions_to_cpm),
        requested_crashes[0])
