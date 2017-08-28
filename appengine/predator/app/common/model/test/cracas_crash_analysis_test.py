# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json

from common.appengine_testcase import AppengineTestCase
from common.model.cracas_crash_analysis import CracasCrashAnalysis


class CracasCrashAnalysisTest(AppengineTestCase):

  def testDoNotUseIdentifiersToSetProperties(self):
    crash_identifiers = {
      'chrome_version': '1',
      'signature': 'signature/here',
      'channel': 'canary',
      'platform': 'win',
      'process_type': 'browser',
    }
    CracasCrashAnalysis.Create(crash_identifiers).put()
    analysis = CracasCrashAnalysis.Get(crash_identifiers)
    self.assertIsNone(analysis.crashed_version)
    self.assertIsNone(analysis.signature)
    self.assertIsNone(analysis.channel)
    self.assertIsNone(analysis.platform)

  def testToJson(self):
    """Tests ``ToJson`` method of CracasCrashAnalysis."""
    crash_identifiers = {
      'signature': 'signature/here',
    }
    CracasCrashAnalysis.Create(crash_identifiers).put()
    analysis = CracasCrashAnalysis.Get(crash_identifiers)
    analysis.stack_trace = json.dumps(['stack_trace1', 'stack_trace2'])

    self.assertEqual(analysis.ToJson()['stack_trace'],
                     ['stack_trace1', 'stack_trace2'])
