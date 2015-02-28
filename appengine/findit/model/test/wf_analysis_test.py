# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model.wf_analysis import WfAnalysis
from model import wf_analysis_status


class WfAnalysisTest(unittest.TestCase):
  def testWfAnalysisStatusIsCompleted(self):
    for status in (wf_analysis_status.ANALYZED, wf_analysis_status.ERROR):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = status
      self.assertTrue(analysis.completed)

  def testWfAnalysisStatusIsNotCompleted(self):
    for status in (wf_analysis_status.PENDING, wf_analysis_status.ANALYZING):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = status
      self.assertFalse(analysis.completed)

  def testWfAnalysisStatusIsFailed(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.status = wf_analysis_status.ERROR
    self.assertTrue(analysis.failed)

  def testWfAnalysisStatusIsNotFailed(self):
    for status in (wf_analysis_status.PENDING, wf_analysis_status.ANALYZING,
                   wf_analysis_status.ANALYZED):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = status
      self.assertFalse(analysis.failed)
