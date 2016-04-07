# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

import unittest

from model.wf_analysis import WfAnalysis
from model import analysis_status
from model import result_status


class WfAnalysisTest(unittest.TestCase):
  def testWfAnalysisStatusIsCompleted(self):
    for status in (analysis_status.COMPLETED, analysis_status.ERROR):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = status
      self.assertTrue(analysis.completed)

  def testWfAnalysisStatusIsNotCompleted(self):
    for status in (analysis_status.PENDING, analysis_status.RUNNING):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = status
      self.assertFalse(analysis.completed)

  def testWfAnalysisDurationWhenNotCompleted(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.status = analysis_status.RUNNING
    self.assertIsNone(analysis.duration)

  def testWfAnalysisDurationWhenStartTimeNotSet(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.status = analysis_status.COMPLETED
    analysis.end_time = datetime(2015, 07, 30, 21, 15, 30, 40)
    self.assertIsNone(analysis.duration)

  def testWfAnalysisDurationWhenEndTimeNotSet(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.status = analysis_status.COMPLETED
    analysis.start_time = datetime(2015, 07, 30, 21, 15, 30, 40)
    self.assertIsNone(analysis.duration)

  def testWfAnalysisDurationWhenCompleted(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.status = analysis_status.COMPLETED
    analysis.start_time = datetime(2015, 07, 30, 21, 15, 30, 40)
    analysis.end_time = datetime(2015, 07, 30, 21, 16, 15, 50)
    self.assertEqual(45, analysis.duration)

  def testWfAnalysisStatusIsFailed(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.status = analysis_status.ERROR
    self.assertTrue(analysis.failed)

  def testWfAnalysisStatusIsNotFailed(self):
    for status in (analysis_status.PENDING, analysis_status.RUNNING,
                   analysis_status.COMPLETED):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = status
      self.assertFalse(analysis.failed)

  def testWfAnalysisStatusDescription(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.status = analysis_status.PENDING
    self.assertEqual("Pending", analysis.status_description)
    analysis.status = analysis_status.RUNNING
    self.assertEqual("Running", analysis.status_description)
    analysis.status = analysis_status.COMPLETED
    self.assertEqual("Completed", analysis.status_description)
    analysis.status = analysis_status.ERROR
    self.assertEqual("Error", analysis.status_description)

  def testWfAnalysisResultStatusDescription(self):
    analysis = WfAnalysis.Create('m', 'b', 123)

    self.assertEqual('', analysis.result_status_description)
    analysis.result_status = result_status.FOUND_CORRECT
    self.assertEqual("Correct - Found", analysis.result_status_description)

  def testWfAnalysisCorrectnessIsUnknownIfIncompletedOrFailed(self):
    for status in (analysis_status.PENDING, analysis_status.RUNNING,
                   analysis_status.ERROR):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = status
      self.assertIsNone(analysis.correct)

  def testWfAnalysisCorrectnessIsUnknownIfUntriaged(self):
    for status in (result_status.FOUND_UNTRIAGED,
                          result_status.NOT_FOUND_UNTRIAGED):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = analysis_status.COMPLETED
      analysis.result_status = status
      self.assertIsNone(analysis.correct)

  def testWfAnalysisHasCorrectResult(self):
    for status in (
        result_status.FOUND_CORRECT,
        result_status.NOT_FOUND_CORRECT,
        result_status.FOUND_CORRECT_DUPLICATE):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = analysis_status.COMPLETED
      analysis.result_status = status
      self.assertTrue(analysis.correct)

  def testWfAnalysisHasIncorrectResult(self):
    for status in (
        result_status.FOUND_INCORRECT,
        result_status.NOT_FOUND_INCORRECT,
        result_status.FOUND_INCORRECT_DUPLICATE):
      analysis = WfAnalysis.Create('m', 'b', 123)
      analysis.status = analysis_status.COMPLETED
      analysis.result_status = status
      self.assertFalse(analysis.correct)
