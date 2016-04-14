# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from crash.test.crash_testcase import CrashTestCase
from model import analysis_status
from model import result_status
from model.crash.fracas_crash_analysis import FracasCrashAnalysis


class FracasCrashAnalysisTest(CrashTestCase):
  def testComputedProperties(self):
    channel = 'canary'
    platform = 'win'
    signature = 'signature/here'
    FracasCrashAnalysis.Create(channel, platform, signature).put()
    analysis = FracasCrashAnalysis.Get(channel, platform, signature)
    self.assertEqual(channel, analysis.channel)
    self.assertEqual(platform, analysis.platform)
    self.assertEqual(signature, analysis.signature)

  def testFracasCrashAnalysisReset(self):
    analysis = FracasCrashAnalysis()
    analysis.versions_to_cpm = {}
    analysis.Reset()
    self.assertIsNone(analysis.versions_to_cpm)
