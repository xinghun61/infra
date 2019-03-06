# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging
import mock

from common.waterfall import buildbucket_client
from dto.commit_id_range import CommitID
from dto.commit_id_range import CommitIDRange
from dto.int_range import IntRange
from gae_libs.testcase import TestCase
from libs import analysis_status
from model import result_status
from model import triage_status
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.data_point import DataPoint
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.isolated_target import IsolatedTarget
from waterfall.build_info import BuildInfo


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
    analysis.status = analysis_status.RUNNING
    analysis.correct_regression_range = True
    analysis.correct_culprit = False
    analysis.correct_culprit = None
    analysis.data_points = [DataPoint()]
    analysis.suspected_flake_build_number = 123
    analysis.suspect_urlsafe_keys = ['some_key']
    analysis.culprit_urlsafe_key = FlakeCulprit.Create('r', 'a1b2c3d4', 12345,
                                                       'url').key.urlsafe()
    analysis.Reset()

    self.assertEqual(analysis_status.PENDING, analysis.status)
    self.assertIsNone(analysis.correct_regression_range)
    self.assertIsNone(analysis.correct_culprit)
    self.assertIsNone(analysis.suspected_flake_build_number)
    self.assertEqual([], analysis.suspect_urlsafe_keys)
    self.assertEqual([], analysis.data_points)
    self.assertIsNone(analysis.culprit_urlsafe_key)

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

  def testGetErrorExistingError(self):
    error = {'title': 'title', 'description': 'description'}
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.error = error
    analysis.Save()

    self.assertEqual(error, analysis.GetError())

  def testGetErrorGenericError(self):
    expected_error = {
        'title': 'Flake analysis encountered an unknown error',
        'description': 'unknown'
    }
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()

    self.assertEqual(expected_error, analysis.GetError())

  def testGetDataPointsWithinCommitPositionRange(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=1000),
        DataPoint.Create(commit_position=1005),
        DataPoint.Create(commit_position=1007),
        DataPoint.Create(commit_position=1010)
    ]
    self.assertEqual(
        analysis.data_points[-2:],
        analysis.GetDataPointsWithinCommitPositionRange(
            IntRange(lower=1007, upper=2000)))
    self.assertEqual([analysis.data_points[0]],
                     analysis.GetDataPointsWithinCommitPositionRange(
                         IntRange(lower=None, upper=1000)))
    self.assertEqual([analysis.data_points[-1]],
                     analysis.GetDataPointsWithinCommitPositionRange(
                         IntRange(lower=1010, upper=None)))
    self.assertEqual(
        analysis.data_points,
        analysis.GetDataPointsWithinCommitPositionRange(
            IntRange(lower=None, upper=None)))

  def testGetLatestRegressionRangeRangeNoDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = []
    self.assertEqual(
        CommitIDRange(lower=None, upper=None),
        analysis.GetLatestRegressionRange())

  def testGetLatestRegressionRangeRangeNoUpperBound(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5, git_hash='rev100')
    ]

    self.assertEqual(
        CommitIDRange(
            lower=None, upper=CommitID(commit_position=100, revision='rev100')),
        analysis.GetLatestRegressionRange())

  def testGetLatestRegressionRangeRangeNoLowerBound(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=100, pass_rate=1.0, git_hash='rev100')
    ]
    self.assertEqual(
        CommitIDRange(
            lower=CommitID(commit_position=100, revision='rev100'), upper=None),
        analysis.GetLatestRegressionRange())

  def testGetLatestRegressionRangeNoUpperBoundMultipleDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.5),
        DataPoint.Create(commit_position=90, pass_rate=0.5, git_hash='rev90')
    ]
    self.assertEqual(
        CommitIDRange(
            lower=None, upper=CommitID(commit_position=90, revision='rev90')),
        analysis.GetLatestRegressionRange())

  def testGetLatestRegressionRange(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=91, pass_rate=0.9, git_hash='rev91'),
        DataPoint.Create(commit_position=90, pass_rate=1.0, git_hash='rev90'),
    ]
    self.assertEqual(
        CommitIDRange(
            lower=CommitID(commit_position=90, revision='rev90'),
            upper=CommitID(commit_position=91, revision='rev91')),
        analysis.GetLatestRegressionRange())

  def testGetLatestRegressionRangeIgnoreRecentStable(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=100, pass_rate=1.0),
        DataPoint.Create(commit_position=91, pass_rate=0.9, git_hash='rev91'),
        DataPoint.Create(commit_position=90, pass_rate=1.0, git_hash='rev90'),
    ]
    self.assertEqual(
        CommitIDRange(
            lower=CommitID(commit_position=90, revision='rev90'),
            upper=CommitID(commit_position=91, revision='rev91')),
        analysis.GetLatestRegressionRange())

  def testGetLatestRegressionRangeMultipleRanges(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=95, pass_rate=0.6, git_hash='rev95'),
        DataPoint.Create(commit_position=92, pass_rate=1.0, git_hash='rev92'),
        DataPoint.Create(commit_position=91, pass_rate=0.9),
        DataPoint.Create(commit_position=90, pass_rate=1.0),
    ]
    self.assertEqual(
        CommitIDRange(
            lower=CommitID(commit_position=92, revision='rev92'),
            upper=CommitID(commit_position=95, revision='rev95')),
        analysis.GetLatestRegressionRange())

  def testGetLatestRegressionRangeMultipleDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=96, pass_rate=0.8),
        DataPoint.Create(commit_position=95, pass_rate=0.9, git_hash='rev95'),
        DataPoint.Create(commit_position=94, pass_rate=0.0, git_hash='rev94'),
        DataPoint.Create(commit_position=93, pass_rate=0.6),
        DataPoint.Create(commit_position=92, pass_rate=1.0),
        DataPoint.Create(commit_position=91, pass_rate=0.9),
        DataPoint.Create(commit_position=90, pass_rate=1.0),
    ]
    self.assertEqual(
        CommitIDRange(
            lower=CommitID(commit_position=94, revision='rev94'),
            upper=CommitID(commit_position=95, revision='rev95')),
        analysis.GetLatestRegressionRange())

  def testInitializeRunning(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.Save()
    analysis.InitializeRunning()

    self.assertEqual(analysis_status.RUNNING, analysis.status)

  def testInitializeRunningAlreadyRunning(self):
    start_time = datetime(2018, 1, 1)
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.status = analysis_status.RUNNING
    analysis.start_time = start_time
    analysis.Save()
    analysis.InitializeRunning()

    self.assertEqual(analysis_status.RUNNING, analysis.status)
    self.assertEqual(start_time, analysis.start_time)

  def testUpdateSuspectedBuildExistingSuspectedBuild(self):
    lower_bound_commit_position = 90
    upper_bound_commit_position = 100
    build_id = 1000

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=upper_bound_commit_position),
        DataPoint.Create(commit_position=lower_bound_commit_position),
    ]
    analysis.suspected_flake_build_number = 123
    analysis.Save()

    lower_bound_target = IsolatedTarget.Create(build_id - 1, '', '', 'm', 'b',
                                               '', '', '', '', '', '',
                                               lower_bound_commit_position, '')
    upper_bound_target = IsolatedTarget.Create(build_id, '', '', 'm', 'b', '',
                                               '', '', '', '', '',
                                               upper_bound_commit_position, '')

    analysis.UpdateSuspectedBuild(lower_bound_target, upper_bound_target)

    self.assertEqual(123, analysis.suspected_flake_build_number)

  def testUpdateSuspectedBuildRegressionRangeTooWide(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=100),
        DataPoint.Create(commit_position=80),
    ]
    analysis.Save()

    lower_bound_target = IsolatedTarget.Create(999, '', '', 'm', 'b', '', '',
                                               '', '', '', '', 90, '')
    upper_bound_target = IsolatedTarget.Create(1000, '', '', 'm', 'b', '', '',
                                               '', '', '', '', 100, '')

    analysis.UpdateSuspectedBuild(lower_bound_target, upper_bound_target)
    self.assertIsNone(analysis.suspected_flake_build_number)

  @mock.patch.object(buildbucket_client, 'GetBuildNumberFromBuildId')
  def testUpdateSuspectedBuild(self, mock_build_number):
    build_number = 120
    build_id = 1200
    mock_build_number.return_value = build_number

    lower_bound_commit_position = 90
    upper_bound_commit_position = 100

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(
            commit_position=upper_bound_commit_position, pass_rate=0.4),
        DataPoint.Create(
            commit_position=lower_bound_commit_position, pass_rate=1.0),
    ]
    analysis.Save()

    lower_bound_target = IsolatedTarget.Create(build_id - 1, '', '', 'm', 'b',
                                               '', '', '', '', '', '',
                                               lower_bound_commit_position, '')
    upper_bound_target = IsolatedTarget.Create(build_id, '', '', 'm', 'b', '',
                                               '', '', '', '', '',
                                               upper_bound_commit_position, '')

    analysis.UpdateSuspectedBuild(lower_bound_target, upper_bound_target)

    self.assertEqual(build_id, analysis.suspected_build_id)
    self.assertEqual(build_number, analysis.suspected_flake_build_number)

  def testUpdateSuspectedBuildUsingBuildInfo(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=100, pass_rate=0.4),
        DataPoint.Create(commit_position=90, pass_rate=1.0),
    ]
    analysis.Save()

    lower_bound_build = BuildInfo('m', 'b', 122)
    lower_bound_build.commit_position = 90
    upper_bound_build = BuildInfo('m', 'b', 123)
    upper_bound_build.commit_position = 100

    analysis.UpdateSuspectedBuildUsingBuildInfo(lower_bound_build,
                                                upper_bound_build)

    self.assertEqual(123, analysis.suspected_flake_build_number)

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
    analysis.status = analysis_status.COMPLETED
    analysis.Update(status=analysis_status.COMPLETED)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)

  def testFindMatchingDataPoint(self):
    old_data_point = DataPoint.Create(
        commit_position=1, pass_rate=1.0, iterations=10)
    new_data_point = DataPoint.Create(
        commit_position=2, pass_rate=0.5, iterations=10)

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [old_data_point]
    self.assertIsNone(analysis.FindMatchingDataPointWithCommitPosition(None))
    self.assertIsNone(
        analysis.FindMatchingDataPointWithCommitPosition(
            new_data_point.commit_position))
    self.assertEqual(
        old_data_point,
        analysis.FindMatchingDataPointWithCommitPosition(
            old_data_point.commit_position))

  @mock.patch.object(logging, 'info')
  def testLogInfo(self, mocked_logging_info):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.LogInfo('message')
    self.assertTrue(mocked_logging_info.called)

  @mock.patch.object(logging, 'warning')
  def testLogWarning(self, mocked_logging_warning):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.LogWarning('message')
    self.assertTrue(mocked_logging_warning.called)

  @mock.patch.object(logging, 'error')
  def testLogError(self, mocked_logging_error):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.LogError('message')
    self.assertTrue(mocked_logging_error.called)

  def testCanRunHeuristicAnalysisAlreadyRan(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 123
    analysis.heuristic_analysis_status = analysis_status.COMPLETED

    self.assertFalse(analysis.CanRunHeuristicAnalysis())

  def testCanRunHeuristicAnalysisNotYetRan(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_build_id = 123
    analysis.heuristic_analysis_status = analysis_status.PENDING

    self.assertTrue(analysis.CanRunHeuristicAnalysis())

  def testCanRunHeuristicAnalysisNoSuspectedBuild(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.heuristic_analysis_status = analysis_status.PENDING

    self.assertFalse(analysis.CanRunHeuristicAnalysis())

  def testGetLowestUpperBoundBuildNumberNoBuildNumbers(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    self.assertEqual(123, analysis.GetLowestUpperBoundBuildNumber(1000))

  def testGetLowestUpperBoundBuildNumber(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(build_number=123, commit_position=1000),
        DataPoint.Create(build_number=122, commit_position=990)
    ]
    self.assertEqual(122, analysis.GetLowestUpperBoundBuildNumber(900))

  def testGetRepresentativeSwarmingTaskIdNoDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    self.assertIsNone(analysis.GetRepresentativeSwarmingTaskId())

  def testGetRepresentativeSwarmingTaskId(self):
    task_id = 'task_id'
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [DataPoint.Create(task_ids=[task_id])]
    self.assertEqual(task_id, analysis.GetRepresentativeSwarmingTaskId())

  def testGetLatestDataPointNoRecentFlakinessPoints(self):
    expected_data_point = DataPoint.Create(commit_position=1000)
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        expected_data_point,
        DataPoint.Create(commit_position=990)
    ]
    self.assertEqual(expected_data_point, analysis.GetLatestDataPoint())

  def testGetLatestDataPointWithRecentFlakinessPoints(self):
    expected_data_point = DataPoint.Create(commit_position=1000)
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = [
        DataPoint.Create(commit_position=990),
        DataPoint.Create(commit_position=980)
    ]
    analysis.flakiness_verification_data_points = [
        expected_data_point,
        DataPoint.Create(commit_position=995)
    ]
    self.assertEqual(expected_data_point, analysis.GetLatestDataPoint())

  def testGetLatestDataPointNoDataPoints(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    self.assertIsNone(analysis.GetLatestDataPoint())
