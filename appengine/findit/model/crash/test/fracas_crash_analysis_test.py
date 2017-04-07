# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from crash.test.predator_testcase import PredatorTestCase
from libs import analysis_status
from model import result_status
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


class FracasCrashAnalysisTest(PredatorTestCase):

  def testDoNotUseIdentifiersToSetProperties(self):
    crash_identifiers = {
      'chrome_version': '1',
      'signature': 'signature/here',
      'channel': 'canary',
      'platform': 'win',
      'process_type': 'browser',
    }
    FracasCrashAnalysis.Create(crash_identifiers).put()
    analysis = FracasCrashAnalysis.Get(crash_identifiers)
    self.assertIsNone(analysis.crashed_version)
    self.assertIsNone(analysis.signature)
    self.assertIsNone(analysis.channel)
    self.assertIsNone(analysis.platform)
