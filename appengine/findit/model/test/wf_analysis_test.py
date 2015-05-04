# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from model import wf_analysis_result_status


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

  def testWfAnalysisStatusDescription(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.status = wf_analysis_status.PENDING
    self.assertEqual("Pending", analysis.status_description)
    analysis.status = wf_analysis_status.ANALYZING
    self.assertEqual("Analyzing", analysis.status_description)
    analysis.status = wf_analysis_status.ANALYZED
    self.assertEqual("Analyzed", analysis.status_description)
    analysis.status = wf_analysis_status.ERROR
    self.assertEqual("Error", analysis.status_description)

  def testWfAnalysisResultStatusDescription(self):
    analysis = WfAnalysis.Create('m', 'b', 123)

    self.assertEqual('', analysis.result_status_description)
    analysis.result_status = wf_analysis_result_status.FOUND_CORRECT
    self.assertEqual("Correct - Found", analysis.result_status_description)

  def testWfAnalysisCorrectnessIsUnknownIfIncompletedOrFailed(self):
    for status in (wf_analysis_status.PENDING, wf_analysis_status.ANALYZING,
                   wf_analysis_status.ERROR):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = status
      self.assertIsNone(analysis.correct)

  def testWfAnalysisCorrectnessIsUnknownIfUntriaged(self):
    for result_status in (wf_analysis_result_status.FOUND_UNTRIAGED,
                          wf_analysis_result_status.NOT_FOUND_UNTRIAGED):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = wf_analysis_status.ANALYZED
      analysis.result_status = result_status
      self.assertIsNone(analysis.correct)

  def testWfAnalysisHasCorrectResult(self):
    for result_status in (wf_analysis_result_status.FOUND_CORRECT,
                          wf_analysis_result_status.NOT_FOUND_CORRECT):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = wf_analysis_status.ANALYZED
      analysis.result_status = result_status
      self.assertTrue(analysis.correct)

  def testWfAnalysisHasIncorrectResult(self):
    for result_status in (wf_analysis_result_status.FOUND_INCORRECT,
                          wf_analysis_result_status.NOT_FOUND_INCORRECT):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = wf_analysis_status.ANALYZED
      analysis.result_status = result_status
      self.assertFalse(analysis.correct)
