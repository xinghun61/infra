# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from gae_libs.testcase import TestCase

from libs import analysis_status
from model import result_status
from model import triage_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis


class MasterFlakeAnalysisTest(TestCase):

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
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's on OS', 't')
    self.assertEqual('s on OS', analysis.step_name)
    self.assertEqual('s', analysis.canonical_step_name)
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

  def testMasterFlakeAnalysisUpdateTriageResultCorrectCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.UpdateTriageResult(
        triage_status.TRIAGED_CORRECT, {'culprit_revision': 'rev'}, 'test')
    self.assertEqual(analysis.result_status, result_status.FOUND_CORRECT)
    self.assertTrue(analysis.correct_culprit)

  def testMasterFlakeAnalysisUpdateTriageResultIncorrectCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.UpdateTriageResult(
        triage_status.TRIAGED_INCORRECT, {'culprit_revision': 'rev'}, 'test')
    self.assertEqual(analysis.result_status, result_status.FOUND_INCORRECT)
    self.assertFalse(analysis.correct_culprit)

  def testReset(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.swarming_rerun_results = [{}]
    analysis.status = analysis_status.RUNNING
    analysis.correct_regression_range = True
    analysis.correct_culprit = False
    analysis.correct_culprit = None
    analysis.data_points = [DataPoint()]
    analysis.suspected_flake_build_number = 123
    analysis.culprit = FlakeCulprit.Create('r', 'a1b2c3d4', 12345, 'url')
    analysis.try_job_status = analysis_status.COMPLETED
    analysis.Reset()

    self.assertEqual([], analysis.swarming_rerun_results)
    self.assertEqual(analysis_status.PENDING, analysis.status)
    self.assertIsNone(analysis.correct_regression_range)
    self.assertIsNone(analysis.correct_culprit)
    self.assertIsNone(analysis.suspected_flake_build_number)
    self.assertEqual([], analysis.data_points)
    self.assertIsNone(analysis.culprit)
    self.assertIsNone(analysis.try_job_status)

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

  def testGetDataPointOfSuspectedBuildNoSuspectedFlakeBuildNumber(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    self.assertIsNone(analysis.GetDataPointOfSuspectedBuild())

  def testGetDataPointOfSuspectedBuild(self):
    expected_build_number = 123
    data_point = DataPoint()
    data_point.build_number = expected_build_number

    analysis = MasterFlakeAnalysis.Create('m', 'b', 125, 's', 't')
    analysis.suspected_flake_build_number = expected_build_number
    analysis.data_points.append(data_point)

    suspected_data_point = analysis.GetDataPointOfSuspectedBuild()
    self.assertEqual(expected_build_number, suspected_data_point.build_number)

  def testGetDataPointOfSuspectedBuildNoDataPoint(self):
    # This scenario should not happen.
    expected_build_number = 123
    unexpected_build_number = 124
    data_point = DataPoint()
    data_point.build_number = expected_build_number

    analysis = MasterFlakeAnalysis.Create('m', 'b', 125, 's', 't')
    analysis.suspected_flake_build_number = unexpected_build_number
    analysis.data_points.append(data_point)

    self.assertIsNone(analysis.GetDataPointOfSuspectedBuild())

  def testGetCommitPosition(self):
    data_point = DataPoint()
    data_point.blame_list = ['r1', 'r2', 'r3']
    data_point.commit_position = 100
    data_point.previous_build_commit_position = 97

    self.assertEqual(98, data_point.GetCommitPosition('r1'))
    self.assertEqual(99, data_point.GetCommitPosition('r2'))
    self.assertEqual(100, data_point.GetCommitPosition('r3'))

  def testGetRevisionAtCommitPosition(self):
    data_point = DataPoint()
    data_point.blame_list = ['r1', 'r2', 'r3']
    data_point.commit_position = 100

    self.assertEqual('r1', data_point.GetRevisionAtCommitPosition(98))
    self.assertEqual('r2', data_point.GetRevisionAtCommitPosition(99))
    self.assertEqual('r3', data_point.GetRevisionAtCommitPosition(100))

  def testGetDictOfCommitPositionAndRevision(self):
    data_point = DataPoint()
    data_point.blame_list = ['r1', 'r2', 'r3']
    data_point.commit_position = 100

    expected_CLs = {
        100: 'r3',
        99: 'r2',
        98: 'r1'
    }

    self.assertEqual(expected_CLs,
                     data_point.GetDictOfCommitPositionAndRevision())
