# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging
import mock

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
    analysis.UpdateTriageResult(triage_status.TRIAGED_CORRECT,
                                {'build_number': 100}, 'test')
    self.assertEqual(analysis.result_status, result_status.FOUND_CORRECT)

  def testMasterFlakeAnalysisUpdateTriageResultIncorrect(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.UpdateTriageResult(triage_status.TRIAGED_INCORRECT,
                                {'build_number': 100}, 'test')
    self.assertEqual(analysis.result_status, result_status.FOUND_INCORRECT)

  def testMasterFlakeAnalysisUpdateTriageResultCorrectCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.UpdateTriageResult(triage_status.TRIAGED_CORRECT,
                                {'culprit_revision': 'rev'}, 'test')
    self.assertEqual(analysis.result_status, result_status.FOUND_CORRECT)
    self.assertTrue(analysis.correct_culprit)

  def testMasterFlakeAnalysisUpdateTriageResultIncorrectCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.UpdateTriageResult(triage_status.TRIAGED_INCORRECT,
                                {'culprit_revision': 'rev'}, 'test')
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
    analysis.culprit_urlsafe_key = FlakeCulprit.Create('r', 'a1b2c3d4', 12345,
                                                       'url').key.urlsafe()
    analysis.try_job_status = analysis_status.COMPLETED
    analysis.Reset()

    self.assertEqual([], analysis.swarming_rerun_results)
    self.assertEqual(analysis_status.PENDING, analysis.status)
    self.assertIsNone(analysis.correct_regression_range)
    self.assertIsNone(analysis.correct_culprit)
    self.assertIsNone(analysis.suspected_flake_build_number)
    self.assertEqual([], analysis.data_points)
    self.assertIsNone(analysis.culprit_urlsafe_key)
    self.assertIsNone(analysis.try_job_status)

  def testGetErrorMessage(self):
    cases = [
        (None, None),
        ('error', {
            'message': 'error',
            'code': 'code'
        }),
    ]
    for expected_error_message, error in cases:
      analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
      analysis.error = error
      self.assertEqual(expected_error_message, analysis.error_message)

  def testGetIterationsToRerun(self):
    cases = [
        (-1, {}),
        (5, {
            'key': 'value',
            'iterations_to_rerun': 5
        }),
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

    key = MasterFlakeAnalysis.Create(master_name, builder_name, build_number,
                                     step_name, test_name).key

    self.assertEqual((None, None),
                     MasterFlakeAnalysis.GetBuildConfigurationFromKey(None))
    self.assertEqual((master_name, builder_name),
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

    expected_CLs = {100: 'r3', 99: 'r2', 98: 'r1'}

    self.assertEqual(expected_CLs,
                     data_point.GetDictOfCommitPositionAndRevision())

  def testGetCommitPositionOfBuild(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(build_number=100, commit_position=1000),
        DataPoint.Create(build_number=101, commit_position=1100)
    ]
    self.assertIsNone(analysis.GetCommitPositionOfBuild(102))
    self.assertEqual(1000, analysis.GetCommitPositionOfBuild(100))

  def testGetCommitPositionOfBuildNoDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    self.assertIsNone(analysis.GetCommitPositionOfBuild(102))

  def testGetDataPointsWithinBuildNumberRange(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(build_number=100, commit_position=1000),
        DataPoint.Create(build_number=101, commit_position=1100),
        DataPoint.Create(build_number=110, commit_position=2000)
    ]
    self.assertEqual(analysis.data_points,
                     analysis.GetDataPointsWithinBuildNumberRange(100, 110))
    self.assertEqual([analysis.data_points[-1]],
                     analysis.GetDataPointsWithinBuildNumberRange(110, 120))
    self.assertEqual(analysis.data_points,
                     analysis.GetDataPointsWithinBuildNumberRange(None, None))

  def testGetDataPointsWithinBuildNumberRangeNoDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    self.assertEqual([], analysis.GetDataPointsWithinBuildNumberRange(100, 110))

  def testGetDataPointsWithinCommitPositionRange(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1000),
        DataPoint.Create(commit_position=1005),
        DataPoint.Create(commit_position=1007),
        DataPoint.Create(commit_position=1010)
    ]
    self.assertEqual(analysis.data_points[-2:],
                     analysis.GetDataPointsWithinCommitPositionRange(
                         1007, 2000))

  def testRemoveDataPointWithBuildNumber(self):
    data_points = [
        DataPoint.Create(build_number=100, commit_position=1000),
        DataPoint.Create(build_number=101, commit_position=1100),
        DataPoint.Create(build_number=110, commit_position=2000)
    ]
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = data_points
    analysis.RemoveDataPointWithBuildNumber(110)

    self.assertEqual(data_points[:-1], analysis.data_points)

  def testRemoveDataPointWithBuildNumberNoDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.RemoveDataPointWithBuildNumber(110)

    self.assertEqual([], analysis.data_points)

  def testRemoveDataPointWithCommitPosition(self):
    data_points = [
        DataPoint.Create(build_number=100, commit_position=1000),
        DataPoint.Create(build_number=101, commit_position=1100),
        DataPoint.Create(build_number=110, commit_position=2000)
    ]
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = data_points
    analysis.RemoveDataPointWithCommitPosition(2000)

    self.assertEqual(data_points[:-1], analysis.data_points)

  def testRemoveDataPointWithCommitPositionNoDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.RemoveDataPointWithCommitPosition(1100)

    self.assertEqual([], analysis.data_points)

  def testUpdate(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Update(status=analysis_status.COMPLETED)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)

  def testUpdateSameValue(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.try_job_status = analysis_status.COMPLETED
    analysis.Update(try_job_status=analysis_status.COMPLETED)
    self.assertEqual(analysis_status.COMPLETED, analysis.try_job_status)

  def testFindMatchingDataPoint(self):
    old_data_point = DataPoint.Create(
        commit_position=1,
        pass_rate=1.0,
        iterations=10,
        blame_list=['r1', 'r2'])
    new_data_point = DataPoint.Create(
        commit_position=2,
        pass_rate=0.5,
        iterations=10,
        blame_list=['r1', 'r2'])

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [old_data_point]
    self.assertIsNone(analysis.FindMatchingDataPointWithCommitPosition(None))
    self.assertIsNone(
        analysis.FindMatchingDataPointWithCommitPosition(
            new_data_point.commit_position))
    self.assertEqual(old_data_point,
                     analysis.FindMatchingDataPointWithCommitPosition(
                         old_data_point.commit_position))

  def testFindMatchingDataPointWithBuildNumber(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(build_number=100),
        DataPoint.Create(build_number=103),
        DataPoint.Create(build_number=200),
        DataPoint.Create(commit_position=1000)
    ]
    self.assertEqual(
        100, analysis.FindMatchingDataPointWithBuildNumber(100).build_number)
    self.assertIsNone(analysis.FindMatchingDataPointWithBuildNumber(105))
    self.assertIsNone(analysis.FindMatchingDataPointWithBuildNumber(None))

  def testDataPointMerge(self):
    data_point_1 = DataPoint.Create(
        commit_position=1, pass_rate=1.0, iterations=10)
    data_point_2 = DataPoint.Create(
        commit_position=1, pass_rate=.5, iterations=10)
    data_point_1.Merge(data_point_2)

    expected = DataPoint.Create(
        commit_position=1, pass_rate=0.75, iterations=20)
    self.assertEqual(data_point_1, expected)

  def testDataPointMergeWithZeroIterations(self):
    data_point_1 = DataPoint.Create(commit_position=1, iterations=0)
    data_point_2 = DataPoint.Create(commit_position=1, iterations=0)
    data_point_1.Merge(data_point_2)

    expected = DataPoint.Create(commit_position=1, iterations=0)
    self.assertEqual(data_point_1, expected)

  def testDataPointMergeWithNone(self):
    data_point_1 = DataPoint.Create(commit_position=1)
    data_point_2 = None
    data_point_1.Merge(data_point_2)

    expected = DataPoint.Create(commit_position=1)
    self.assertEqual(data_point_1, expected)

  def testAppendOrMergeWithHit(self):
    data_points = [
        DataPoint.Create(
            commit_position=1,
            pass_rate=1.0,
            iterations=10,
            blame_list=["aa", "bb"])
    ]
    new_data_point = DataPoint.Create(
        commit_position=1,
        pass_rate=0.5,
        iterations=10,
        blame_list=["aa", "bb"])

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = data_points
    analysis.AppendOrMergeDataPoint(new_data_point)

    expected = [
        DataPoint.Create(
            commit_position=1,
            pass_rate=0.75,
            iterations=20,
            blame_list=["aa", "bb"])
    ]
    self.assertEqual(analysis.data_points, expected)

  def testAppendOrMergeWithMiss(self):
    data_points = [
        DataPoint.Create(
            commit_position=1,
            pass_rate=1.0,
            iterations=10,
            blame_list=["aa", "bb"])
    ]
    new_data_point = DataPoint.Create(
        commit_position=2,
        pass_rate=0.5,
        iterations=10,
        blame_list=["bb", "cc"])

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = data_points
    analysis.AppendOrMergeDataPoint(new_data_point)

    expected = [
        DataPoint.Create(
            commit_position=1,
            pass_rate=1.0,
            iterations=10,
            blame_list=["aa", "bb"]),
        DataPoint.Create(
            commit_position=2,
            pass_rate=0.5,
            iterations=10,
            blame_list=["bb", "cc"])
    ]
    self.assertEqual(analysis.data_points, expected)

  @mock.patch.object(logging, 'info')
  def testLogInfo(self, mocked_logging_info):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.LogInfo('message')
    mocked_logging_info.assert_called()

  @mock.patch.object(logging, 'warning')
  def testLogWarning(self, mocked_logging_warning):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.LogWarning('message')
    mocked_logging_warning.assert_called()

  @mock.patch.object(logging, 'error')
  def testLogError(self, mocked_logging_error):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.LogError('message')
    mocked_logging_error.assert_called()
