# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

import unittest

from model import analysis_status
from model import result_status
from model import triage_status
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis


class MasterFlakeAnalysisTest(unittest.TestCase):

  def testMasterFlakeAnalysisStatusIsCompleted(self):
    for status in (analysis_status.COMPLETED, analysis_status.ERROR):
      analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
      analysis.status = status
      self.assertTrue(analysis.completed)

  def testMasterFlakeAnalysisStatusIsNotCompleted(self):
    for status in (analysis_status.PENDING, analysis_status.RUNNING):
      analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
      analysis.status = status
      self.assertFalse(analysis.completed)

  def testMasterFlakeAnalysisDurationWhenNotCompleted(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.RUNNING
    self.assertIsNone(analysis.duration)

  def testMasterFlakeAnalysisDurationWhenStartTimeNotSet(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.end_time = datetime(2015, 07, 30, 21, 15, 30, 40)
    self.assertIsNone(analysis.duration)

  def testMasterFlakeAnalysisDurationWhenEndTimeNotSet(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.start_time = datetime(2015, 07, 30, 21, 15, 30, 40)
    self.assertIsNone(analysis.duration)

  def testMasterFlakeAnalysisDurationWhenCompleted(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.COMPLETED
    analysis.start_time = datetime(2015, 07, 30, 21, 15, 30, 40)
    analysis.end_time = datetime(2015, 07, 30, 21, 16, 15, 50)
    self.assertEqual(45, analysis.duration)

  def testMasterFlakeAnalysisStatusIsFailed(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.ERROR
    self.assertTrue(analysis.failed)

  def testMasterFlakeAnalysisStatusIsNotFailed(self):
    for status in (analysis_status.PENDING, analysis_status.RUNNING,
                   analysis_status.COMPLETED):
      analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
      analysis.status = status
      self.assertFalse(analysis.failed)

  def testMasterFlakeAnalysisStatusDescriptionPending(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.PENDING
    self.assertEqual('Pending', analysis.status_description)

  def testMasterFlakeAnalysisStatusDescriptionRunning(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.RUNNING
    self.assertEqual('Running', analysis.status_description)

  def testMasterFlakeAnalysisStatusDescriptionCompleted(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.COMPLETED
    self.assertEqual('Completed', analysis.status_description)

  def testMasterFlakeAnalysisStatusDescriptionError(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.ERROR
    self.assertEqual('Error', analysis.status_description)

  def testMasterFlakeAnalysisStepTestName(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    self.assertEqual('s', analysis.step_name)
    self.assertEqual('t', analysis.test_name)

  def testMasterFlakeAnalysisUpdateTriageResultCorrect(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.UpdateTriageResult(
        triage_status.TRIAGED_CORRECT, {'build_number': 100}, 'test')
    self.assertEqual(analysis.result_status, result_status.FOUND_CORRECT)

  def testMasterFlakeAnalysisUpdateTriageResultIncorrect(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.UpdateTriageResult(
        triage_status.TRIAGED_INCORRECT, {'build_number': 100}, 'test')
    self.assertEqual(analysis.result_status, result_status.FOUND_INCORRECT)

  def testReset(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.swarming_rerun_results = [{}]
    analysis.status = analysis_status.RUNNING
    analysis.correct_regression_range = True
    analysis.correct_culprit = False
    analysis.correct_culprit = None
    analysis.data_points = [DataPoint()]
    analysis.suspected_flake_build_number = 123
    analysis.Reset()

    self.assertEqual([], analysis.swarming_rerun_results)
    self.assertEqual(analysis_status.PENDING, analysis.status)
    self.assertIsNone(analysis.correct_regression_range)
    self.assertIsNone(analysis.correct_culprit)
    self.assertIsNone(analysis.suspected_flake_build_number)
    self.assertEqual([], analysis.data_points)

  def testGetErrorMessage(self):
    cases = [
        (None, None),
        ('error', {'message': 'error', 'code': 'code'}),
    ]
    for expected_error_message, error in cases:
      analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
      analysis.error = error
      self.assertEqual(expected_error_message, analysis.error_message)

  def testGetIterationsToRerun(self):
    cases = [
        (-1, {}),
        (5, {'key': 'value', 'iterations_to_rerun': 5}),
    ]
    for expected_rerun, algorithm_parameters in cases:
      analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
      analysis.algorithm_parameters = algorithm_parameters
      self.assertEqual(expected_rerun, analysis.iterations_to_rerun)

  def testGetBuildConfigurationFromKey(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    key = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name).key

    self.assertEqual(
        (None, None),
        MasterFlakeAnalysis.GetBuildConfigurationFromKey(None))
    self.assertEqual(
        (master_name, builder_name),
        MasterFlakeAnalysis.GetBuildConfigurationFromKey(key))
