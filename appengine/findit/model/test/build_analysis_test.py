# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model.build_analysis import BuildAnalysis
from model.build_analysis_status import BuildAnalysisStatus


class BuildAnalysisTest(unittest.TestCase):
  def testBuildAnalysisStatusIsCompleted(self):
    for status in (BuildAnalysisStatus.ANALYZED, BuildAnalysisStatus.ERROR):
      analysis = BuildAnalysis.CreateBuildAnalysis('m', 'b', 123)
      analysis.status = status
      self.assertTrue(analysis.completed)

  def testBuildAnalysisStatusIsNotCompleted(self):
    for status in (BuildAnalysisStatus.PENDING, BuildAnalysisStatus.ANALYZING):
      analysis = BuildAnalysis.CreateBuildAnalysis('m', 'b', 123)
      analysis.status = status
      self.assertFalse(analysis.completed)

  def testBuildAnalysisStatusIsFailed(self):
    analysis = BuildAnalysis.CreateBuildAnalysis('m', 'b', 123)
    analysis.status = BuildAnalysisStatus.ERROR
    self.assertTrue(analysis.failed)

  def testBuildAnalysisStatusIsNotFailed(self):
    for status in (BuildAnalysisStatus.PENDING, BuildAnalysisStatus.ANALYZING,
                   BuildAnalysisStatus.ANALYZED):
      analysis = BuildAnalysis.CreateBuildAnalysis('m', 'b', 123)
      analysis.status = status
      self.assertFalse(analysis.failed)
