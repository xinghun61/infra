# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs.gitiles.change_log import ChangeLog

from common import constants
from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from model import analysis_status
from model import result_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake import recursive_flake_try_job_pipeline
from waterfall.flake.recursive_flake_try_job_pipeline import (
    _GetNormalizedTryJobDataPoints)
from waterfall.flake.recursive_flake_try_job_pipeline import CreateCulprit
from waterfall.flake.recursive_flake_try_job_pipeline import (
    NextCommitPositionPipeline)
from waterfall.flake.recursive_flake_try_job_pipeline import (
    RecursiveFlakeTryJobPipeline)
from waterfall.flake.recursive_flake_try_job_pipeline import (
    UpdateAnalysisUponCompletion)
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA


def _GenerateDataPoint(
    pass_rate=None, build_number=None, task_id=None, try_job_url=None,
    commit_position=None, git_hash=None, previous_build_commit_position=None,
    previous_build_git_hash=None, blame_list=None):
  data_point = DataPoint()
  data_point.pass_rate = pass_rate
  data_point.build_number = build_number
  data_point.task_id = task_id
  data_point.try_job_url = try_job_url
  data_point.commit_position = commit_position
  data_point.git_hash = git_hash
  data_point.previous_build_commit_position = previous_build_commit_position
  data_point.previous_build_git_hash = previous_build_git_hash
  data_point.blame_list = blame_list if blame_list else []
  return data_point


class RecursiveFlakeTryJobPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testRecursiveFlakeTryJobPipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    revision = 'r1000'
    try_job_id = 'try_job_id'
    lower_boundary_commit_position = 998

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    iterations_to_rerun = analysis.algorithm_parameters.get(
        'try_job_rerun', {}).get('iterations_to_rerun')

    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)

    try_job_result = {
        revision: {
            step_name: {
                'status': 'failed',
                'failures': [test_name],
                'valid': True,
                'pass_fail_counts': {
                    'test_name': {
                        'pass_count': 28,
                        'fail_count': 72
                    }
                }
            }
        }
    }

    self.MockPipeline(
        recursive_flake_try_job_pipeline.ScheduleFlakeTryJobPipeline,
        try_job_id,
        expected_args=[master_name, builder_name, step_name, test_name,
                       revision, iterations_to_rerun])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.MonitorTryJobPipeline,
        try_job_result,
        expected_args=[try_job.key.urlsafe(), failure_type.FLAKY_TEST,
                       try_job_id])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.ProcessFlakeTryJobResultPipeline,
        None,
        expected_args=[revision, commit_position, try_job_result,
                       try_job.key.urlsafe(), analysis.key.urlsafe()])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.NextCommitPositionPipeline,
        '',
        expected_args=[analysis.key.urlsafe(), try_job.key.urlsafe()])

    pipeline = RecursiveFlakeTryJobPipeline(
        analysis.key.urlsafe(), commit_position, revision,
        lower_boundary_commit_position)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    self.assertIsNotNone(
        FlakeTryJob.Get(master_name, builder_name, step_name, test_name,
                        revision))
    self.assertEqual(analysis.last_attempted_revision, revision)
    self.assertIsNone(analysis.last_attempted_swarming_task_id)

  def testRecursiveFlakeTryJobPipelineDoNotStartIfError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    revision = 'r1000'
    lower_boundary_commit_position = 998

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.status = analysis_status.ERROR
    analysis.Save()

    pipeline = RecursiveFlakeTryJobPipeline(
        analysis.key.urlsafe(), commit_position, revision,
        lower_boundary_commit_position)

    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    self.assertIsNone(analysis.try_job_status)

  def testNextCommitPositionPipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    revision = 'r99'
    try_job_id = '123'

    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)
    try_job.try_job_ids.append(try_job_id)
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.try_job_status = analysis_status.RUNNING
    analysis.data_points = [
        _GenerateDataPoint(
            pass_rate=0.9, commit_position=100, build_number=12345,
            previous_build_commit_position=90, blame_list=[
                'r91', 'r92', 'r93', 'r94', 'r95', 'r96', 'r97', 'r98', 'r99',
                'r100']),
        _GenerateDataPoint(pass_rate=0.9, commit_position=99, try_job_url='u')]
    analysis.suspected_flake_build_number = 12345
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    self.MockPipeline(
        recursive_flake_try_job_pipeline.RecursiveFlakeTryJobPipeline,
        '',
        expected_args=[analysis.key.urlsafe(), 97, 'r97', 90],
        expected_kwargs={})

    pipeline = NextCommitPositionPipeline(
        analysis.key.urlsafe(), try_job.key.urlsafe(), 90)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  def testNextCommitPositionPipelineCompleted(self, mock_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    git_hash = 'r95'
    commit_position = 95
    url = 'url'
    try_job_id = '123'
    change_log = ChangeLog(None, None, git_hash,
                           commit_position, None, None, url, None)
    mock_fn.return_value = change_log

    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, git_hash)
    try_job.try_job_ids.append(try_job_id)
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.try_job_status = analysis_status.RUNNING
    analysis.data_points = [
        _GenerateDataPoint(
            pass_rate=0.9, commit_position=100, build_number=12345,
            previous_build_commit_position=90, blame_list=[
                'r91', 'r92', 'r93', 'r94', 'r95', 'r96', 'r97', 'r98', 'r99',
                'r100']),
        _GenerateDataPoint(pass_rate=0.9, commit_position=99, try_job_url='u1'),
        _GenerateDataPoint(pass_rate=0.9, commit_position=97, try_job_url='u2'),
        _GenerateDataPoint(pass_rate=0.9, commit_position=95, try_job_url='u4'),
        _GenerateDataPoint(pass_rate=1.0, commit_position=94, try_job_url='u3')]
    analysis.suspected_flake_build_number = 12345
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    self.MockPipeline(
        recursive_flake_try_job_pipeline.RecursiveFlakeTryJobPipeline,
        '',
        expected_args=[],
        expected_kwargs={})
    self.MockPipeline(recursive_flake_try_job_pipeline.UpdateFlakeBugPipeline,
                      '',
                      expected_args=[analysis.key.urlsafe()],
                      expected_kwargs={})

    pipeline = NextCommitPositionPipeline(
        analysis.key.urlsafe(), try_job.key.urlsafe(), 90)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    culprit = analysis.culprit
    self.assertEqual(git_hash, culprit.revision)
    self.assertEqual(95, culprit.commit_position)

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  def testNextCommitPositionNewlyAddedFlakyTest(self, mocked_fn):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    git_hash = 'r100'
    try_job_id = '123'
    revision = 'r100'
    commit_position = 100
    url = 'url'
    change_log = ChangeLog(None, None, revision,
                           commit_position, None, None, url, None)
    mocked_fn.return_value = change_log

    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)
    try_job.try_job_ids.append(try_job_id)
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.try_job_status = analysis_status.RUNNING
    analysis.data_points = [
        _GenerateDataPoint(
            pass_rate=0.9, commit_position=commit_position, build_number=12345,
            previous_build_commit_position=98, blame_list=['r99', 'r100']),
        _GenerateDataPoint(pass_rate=-1, commit_position=99, try_job_url='id1')]
    analysis.suspected_flake_build_number = 12345
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    self.MockPipeline(
        recursive_flake_try_job_pipeline.RecursiveFlakeTryJobPipeline,
        '',
        expected_args=[])

    pipeline = NextCommitPositionPipeline(
        analysis.key.urlsafe(), try_job.key.urlsafe(), 98)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    culprit = analysis.culprit
    self.assertEqual(git_hash, culprit.revision)
    self.assertEqual(100, culprit.commit_position)

  @mock.patch(
      ('waterfall.flake.recursive_flake_try_job_pipeline.'
       'RecursiveFlakeTryJobPipeline'))
  def testNextCommitPositionPipelineForFailedTryJob(self, mocked_pipeline):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    revision = 'r97'
    lower_boundary_commit_position = 96
    try_job_id = '123'
    error = {
        'code': 1,
        'message': 'some failure message',
    }

    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)
    try_job.try_job_ids.append(try_job_id)
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.error = error
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.put()

    self.MockPipeline(recursive_flake_try_job_pipeline.UpdateFlakeBugPipeline,
                      '',
                      expected_args=[analysis.key.urlsafe()],
                      expected_kwargs={})

    pipeline = NextCommitPositionPipeline(
        analysis.key.urlsafe(), try_job.key.urlsafe(),
        lower_boundary_commit_position)
    pipeline.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    mocked_pipeline.assert_not_called()
    self.assertEqual(error, analysis.error)

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  def testCreateCulprit(self, mocked_module):
    revision = 'a1b2c3d4'
    commit_position = 12345
    url = 'url'
    repo_name = 'repo_name'
    change_log = ChangeLog(None, None, revision,
                           commit_position, None, None, url, None)
    mocked_module.return_value = change_log
    culprit = CreateCulprit(revision, commit_position, 0.6, repo_name)

    self.assertEqual(commit_position, culprit.commit_position)
    self.assertEqual(revision, culprit.revision)
    self.assertEqual(url, culprit.url)
    self.assertEqual(repo_name, culprit.repo_name)

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog', return_value=None)
  def testCreateCulpritNoLogs(self, _):
    revision = 'a1b2c3d4'
    commit_position = 12345
    repo_name = 'repo_name'
    culprit = CreateCulprit(revision, commit_position, 0.6, repo_name)

    self.assertEqual(commit_position, culprit.commit_position)
    self.assertEqual(revision, culprit.revision)
    self.assertIsNone(culprit.url)
    self.assertEqual(repo_name, culprit.repo_name)

  def testUpdateAnalysisUponCompletionFound(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.last_attempted_revision = 'a1b2c3d4'
    culprit = FlakeCulprit.Create('repo_name', 'a1b2c3d4', 12345, 'url')
    UpdateAnalysisUponCompletion(
        analysis, culprit, analysis_status.COMPLETED, None)
    self.assertIsNone(analysis.error)
    self.assertIsNone(analysis.last_attempted_revision)
    self.assertIsNone(analysis.last_attempted_swarming_task_id)
    self.assertEqual(culprit.revision, analysis.culprit.revision)
    self.assertEqual(analysis_status.COMPLETED, analysis.try_job_status)
    self.assertEqual(result_status.FOUND_UNTRIAGED, analysis.result_status)

  def testUpdateAnalysisUponCompletionNotFound(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.last_attempted_revision = 'a1b2c3d4'
    UpdateAnalysisUponCompletion(
        analysis, None, analysis_status.COMPLETED, None)
    self.assertIsNone(analysis.error)
    self.assertIsNone(analysis.last_attempted_revision)
    self.assertIsNone(analysis.last_attempted_swarming_task_id)
    self.assertIsNone(analysis.culprit)
    self.assertEqual(analysis_status.COMPLETED, analysis.try_job_status)
    self.assertEqual(result_status.NOT_FOUND_UNTRIAGED, analysis.result_status)

  def testUpdateAnalysisUponCompletionError(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.last_attempted_revision = 'a1b2c3d4'
    UpdateAnalysisUponCompletion(
        analysis, None, analysis_status.ERROR, {'error': 'errror'})
    self.assertIsNotNone(analysis.error)
    self.assertEqual('a1b2c3d4', analysis.last_attempted_revision)
    self.assertIsNone(analysis.culprit)
    self.assertEqual(analysis_status.ERROR, analysis.try_job_status)
    self.assertIsNone(analysis.result_status)

  def testGetTryJobDataPointsNoTryJobsYet(self):
    suspected_flake_build_number = 12345
    data_points = [
        _GenerateDataPoint(pass_rate=0.8, commit_position=100,
                           build_number=suspected_flake_build_number)]
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = suspected_flake_build_number
    analysis.data_points = data_points

    normalized_data_points = _GetNormalizedTryJobDataPoints(analysis)
    self.assertEqual(normalized_data_points[0].run_point_number, 100)
    self.assertEqual(normalized_data_points[0].pass_rate, 0.8)
    self.assertEqual(len(normalized_data_points), 1)

  def testGetTryJobDataPointsWithTryJobs(self):
    suspected_flake_build_number = 12345
    all_data_points = [
        _GenerateDataPoint(pass_rate=0.8, commit_position=100,
                           build_number=suspected_flake_build_number),
        _GenerateDataPoint(pass_rate=1.0, commit_position=90,
                           build_number=suspected_flake_build_number - 1),
        _GenerateDataPoint(pass_rate=0.8, commit_position=99,
                           try_job_url='url')]

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = suspected_flake_build_number
    analysis.data_points = all_data_points

    normalized_data_points = _GetNormalizedTryJobDataPoints(analysis)

    self.assertEqual(normalized_data_points[0].run_point_number, 100)
    self.assertEqual(normalized_data_points[0].pass_rate, 0.8)
    self.assertEqual(normalized_data_points[1].run_point_number, 99)
    self.assertEqual(normalized_data_points[1].pass_rate, 0.8)

  @mock.patch.object(RecursiveFlakeTryJobPipeline, 'was_aborted',
                     return_value=True)
  def testRecursiveFlakeTryJobPipelineAborted(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    step_name = 's'
    test_name = 't'
    revision = 'rev'
    commit_position = 1
    build_id = 'b1'
    lower_boundary_commit_position = 0

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.Save()

    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)
    try_job.try_job_ids = [build_id]
    try_job.put()

    try_job_data = FlakeTryJobData.Create(build_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    rftp = RecursiveFlakeTryJobPipeline(
        analysis.key.urlsafe(), commit_position, revision,
        lower_boundary_commit_position)

    rftp._LogUnexpectedAbort()

    expected_error = {
        'error': 'RecursiveFlakeTryJobPipeline was aborted unexpectedly',
        'message': 'RecursiveFlakeTryJobPipeline was aborted unexpectedly'
    }

    self.assertEqual(analysis_status.ERROR, analysis.try_job_status)
    self.assertEqual(expected_error, analysis.error)
    self.assertEqual(analysis_status.ERROR, try_job.status)
    self.assertEqual(expected_error, try_job_data.error)

  @mock.patch.object(RecursiveFlakeTryJobPipeline, 'was_aborted',
                     return_value=True)
  def testRecursiveFlakeTryJobPipelineAbortedNoUpdateCompletedTryJob(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    step_name = 's'
    test_name = 't'
    revision = 'rev'
    commit_position = 1
    lower_boundary_commit_position = 0

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.Save()

    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)
    try_job.status = analysis_status.COMPLETED
    try_job.put()

    rftp = RecursiveFlakeTryJobPipeline(
        analysis.key.urlsafe(), commit_position, revision,
        lower_boundary_commit_position)

    rftp._LogUnexpectedAbort()

    self.assertEqual(analysis_status.COMPLETED, try_job.status)
