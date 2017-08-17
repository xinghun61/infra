# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from google.appengine.ext import ndb

from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs.gitiles.change_log import ChangeLog

from common import constants
from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import swarming_util
from waterfall.flake import confidence
from waterfall.flake import flake_constants
from waterfall.flake import recursive_flake_try_job_pipeline
from waterfall.flake.recursive_flake_try_job_pipeline import (
    _GetNormalizedTryJobDataPoints)
from waterfall.flake.recursive_flake_try_job_pipeline import (
    NextCommitPositionPipeline)
from waterfall.flake.recursive_flake_try_job_pipeline import (
    RecursiveFlakeTryJobPipeline)
from waterfall.flake.send_notification_for_flake_culprit_pipeline import (
    SendNotificationForFlakeCulpritPipeline)
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline
from waterfall.test import wf_testcase
from waterfall.test.wf_testcase import DEFAULT_CONFIG_DATA

_DEFAULT_CACHE_NAME = swarming_util.GetCacheName(None, None)


class RecursiveFlakeTryJobPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testRecursiveFlakeTryJobPipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    upper_bound_commit_position = 1000
    start_commit_position = 999
    revision = 'r999'
    try_job_id = 'try_job_id'
    lower_bound_commit_position = 998
    user_specified_iterations = None

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    iterations_to_rerun = analysis.algorithm_parameters.get(
        'try_job_rerun', {}).get('iterations_to_rerun')

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)

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
        expected_args=[
            master_name, builder_name, step_name, test_name, revision,
            analysis.key.urlsafe(), _DEFAULT_CACHE_NAME, None,
            iterations_to_rerun
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.MonitorTryJobPipeline,
        try_job_result,
        expected_args=[
            try_job.key.urlsafe(), failure_type.FLAKY_TEST, try_job_id
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.ProcessFlakeTryJobResultPipeline,
        None,
        expected_args=[
            revision, start_commit_position, try_job_result,
            try_job.key.urlsafe(),
            analysis.key.urlsafe()
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.NextCommitPositionPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(),
            try_job.key.urlsafe(), lower_bound_commit_position,
            upper_bound_commit_position, user_specified_iterations,
            _DEFAULT_CACHE_NAME, None, False
        ])

    pipeline_job = RecursiveFlakeTryJobPipeline(
        analysis.key.urlsafe(),
        start_commit_position,
        revision,
        lower_bound_commit_position,
        upper_bound_commit_position,
        None,
        _DEFAULT_CACHE_NAME,
        None,
        rerun=False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    self.assertIsNotNone(
        FlakeTryJob.Get(master_name, builder_name, step_name, test_name,
                        revision))
    self.assertEqual(analysis.last_attempted_revision, revision)
    self.assertIsNone(analysis.last_attempted_swarming_task_id)

  def testRecursiveFlakeTryJobPipelineUserRerunRange(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    upper_bound_commit_position = 1000
    lower_bound_commit_position = 998
    start_commit_position = 999
    user_specified_iterations = 200
    revision = 'r999'
    try_job_id = 'try_job_id'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)

    try_job_result = {
        revision: {
            step_name: {
                'status': 'failed',
                'failures': [test_name],
                'valid': True,
                'pass_fail_counts': {
                    test_name: {
                        'pass_count': 28,
                        'fail_count': 72
                    }
                }
            }
        }
    }
    report = {'report': {'result': try_job_result}}
    try_job.flake_results.append(report)
    try_job.put()

    self.MockPipeline(
        recursive_flake_try_job_pipeline.ScheduleFlakeTryJobPipeline,
        try_job_id,
        expected_args=[
            master_name, builder_name, step_name, test_name, revision,
            analysis.key.urlsafe(), _DEFAULT_CACHE_NAME, None,
            user_specified_iterations
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.MonitorTryJobPipeline,
        try_job_result,
        expected_args=[
            try_job.key.urlsafe(), failure_type.FLAKY_TEST, try_job_id
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.ProcessFlakeTryJobResultPipeline,
        None,
        expected_args=[
            revision, start_commit_position, try_job_result,
            try_job.key.urlsafe(),
            analysis.key.urlsafe()
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.NextCommitPositionPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(),
            try_job.key.urlsafe(), lower_bound_commit_position,
            upper_bound_commit_position, user_specified_iterations,
            _DEFAULT_CACHE_NAME, None, False
        ])

    pipeline_job = RecursiveFlakeTryJobPipeline(
        analysis.key.urlsafe(),
        start_commit_position,
        revision,
        lower_bound_commit_position,
        upper_bound_commit_position,
        user_specified_iterations,
        _DEFAULT_CACHE_NAME,
        None,
        rerun=False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    self.assertIsNotNone(
        FlakeTryJob.Get(master_name, builder_name, step_name, test_name,
                        revision))
    self.assertIsNone(analysis.last_attempted_revision)
    self.assertIsNone(analysis.last_attempted_swarming_task_id)

  def testRecursiveFlakeTryJobPipelineDoNotStartIfError(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    commit_position = 1000
    revision = 'r1000'
    lower_bound_commit_position = 998

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.ERROR
    analysis.Save()

    pipeline_job = RecursiveFlakeTryJobPipeline(
        analysis.key.urlsafe(),
        commit_position,
        revision,
        lower_bound_commit_position,
        commit_position,
        None,
        _DEFAULT_CACHE_NAME,
        None,
        rerun=False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
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

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.try_job_ids.append(try_job_id)
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.try_job_status = analysis_status.RUNNING
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=0.9,
            commit_position=100,
            build_number=12345,
            previous_build_commit_position=90,
            blame_list=[
                'r91', 'r92', 'r93', 'r94', 'r95', 'r96', 'r97', 'r98', 'r99',
                'r100'
            ]),
        DataPoint.Create(pass_rate=0.9, commit_position=90)
    ]
    analysis.suspected_flake_build_number = 12345
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    self.MockPipeline(
        recursive_flake_try_job_pipeline.RecursiveFlakeTryJobPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), 95, 'r95', 90, 100, None,
            _DEFAULT_CACHE_NAME, None
        ],
        expected_kwargs={'retries': 0,
                         'rerun': False})

    pipeline_job = NextCommitPositionPipeline(
        analysis.key.urlsafe(),
        try_job.key.urlsafe(), 90, 100, None, _DEFAULT_CACHE_NAME, None, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
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
    change_log = ChangeLog(None, None, git_hash, commit_position, None, None,
                           url, None)
    mock_fn.return_value = change_log

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, git_hash)
    try_job.try_job_ids.append(try_job_id)
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.try_job_status = analysis_status.RUNNING
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=0.9,
            commit_position=100,
            build_number=12345,
            previous_build_commit_position=90,
            blame_list=[
                'r91', 'r92', 'r93', 'r94', 'r95', 'r96', 'r97', 'r98', 'r99',
                'r100'
            ]),
        DataPoint.Create(pass_rate=0.9, commit_position=99, try_job_url='u1'),
        DataPoint.Create(pass_rate=0.9, commit_position=97, try_job_url='u2'),
        DataPoint.Create(pass_rate=0.9, commit_position=95, try_job_url='u4'),
        DataPoint.Create(pass_rate=1.0, commit_position=94, try_job_url='u3')
    ]
    analysis.suspected_flake_build_number = 12345
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    self.MockPipeline(
        recursive_flake_try_job_pipeline.RecursiveFlakeTryJobPipeline,
        '',
        expected_args=[],
        expected_kwargs={})
    self.MockPipeline(
        UpdateFlakeBugPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})
    self.MockPipeline(
        SendNotificationForFlakeCulpritPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline_job = NextCommitPositionPipeline(
        analysis.key.urlsafe(),
        try_job.key.urlsafe(), 90, 100, None, _DEFAULT_CACHE_NAME, None, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
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
    change_log = ChangeLog(None, None, revision, commit_position, None, None,
                           url, None)
    mocked_fn.return_value = change_log

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.try_job_ids.append(try_job_id)
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.try_job_status = analysis_status.RUNNING
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=0.9,
            commit_position=commit_position,
            build_number=12345,
            previous_build_commit_position=98,
            blame_list=['r99', 'r100']),
        DataPoint.Create(pass_rate=-1, commit_position=99, try_job_url='id1'),
        DataPoint.Create(pass_rate=-1, commit_position=98)
    ]
    analysis.suspected_flake_build_number = 12345
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    self.MockPipeline(
        recursive_flake_try_job_pipeline.RecursiveFlakeTryJobPipeline,
        '',
        expected_args=[])
    self.MockPipeline(
        SendNotificationForFlakeCulpritPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline_job = NextCommitPositionPipeline(
        analysis.key.urlsafe(),
        try_job.key.urlsafe(), 98, 100, None, _DEFAULT_CACHE_NAME, None, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
    self.assertEqual(git_hash, culprit.revision)
    self.assertEqual(100, culprit.commit_position)

  @mock.patch(('waterfall.flake.recursive_flake_try_job_pipeline.'
               'RecursiveFlakeTryJobPipeline'))
  def testNextCommitPositionPipelineForFailedTryJob(self, mocked_pipeline):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    revision = 'r97'
    lower_bound_commit_position = 96
    upper_bound_commit_position = 100
    try_job_id = '123'
    error = {
        'code': 1,
        'message': 'some failure message',
    }

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.try_job_ids.append(try_job_id)
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.error = error
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.put()

    self.MockPipeline(
        UpdateFlakeBugPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline_job = NextCommitPositionPipeline(
        analysis.key.urlsafe(),
        try_job.key.urlsafe(), lower_bound_commit_position,
        upper_bound_commit_position, None, _DEFAULT_CACHE_NAME, None, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    mocked_pipeline.assert_not_called()
    self.assertEqual(error, analysis.error)

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  def testUpdateCulpritNewCulprit(self, mocked_fn):
    revision = 'a1b2c3d4'
    commit_position = 12345
    url = 'url'
    repo_name = 'repo_name'
    change_log = ChangeLog(None, None, revision, commit_position, None, None,
                           url, None)
    mocked_fn.return_value = change_log

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')

    culprit = recursive_flake_try_job_pipeline.UpdateCulprit(
        analysis.key.urlsafe(), revision, commit_position, repo_name)

    self.assertIsNotNone(culprit)
    self.assertEqual([analysis.key.urlsafe()],
                     culprit.flake_analysis_urlsafe_keys)
    self.assertEqual(url, culprit.url)
    self.assertEqual(repo_name, culprit.repo_name)
    self.assertEqual(revision, culprit.revision)

  def testUpdateCulpritExistingCulprit(self):
    revision = 'a1b2c3d4'
    commit_position = 12345
    url = 'url'
    repo_name = 'repo_name'
    analysis_urlsafe_key = 'urlsafe_key'

    culprit = FlakeCulprit.Create(repo_name, revision, commit_position)
    culprit.flake_analysis_urlsafe_keys = ['another_analysis_urlsafe_key']
    culprit.url = url
    culprit.put()

    culprit = recursive_flake_try_job_pipeline.UpdateCulprit(
        analysis_urlsafe_key, revision, commit_position, repo_name)

    self.assertIsNotNone(culprit)
    self.assertEqual(2, len(culprit.flake_analysis_urlsafe_keys))
    self.assertIn(analysis_urlsafe_key, culprit.flake_analysis_urlsafe_keys)
    self.assertEqual(url, culprit.url)
    self.assertEqual(repo_name, culprit.repo_name)
    self.assertEqual(revision, culprit.revision)

  def testUpdateCulpritExistingCulpritAlreadyHasAnalyis(self):
    revision = 'a1b2c3d4'
    commit_position = 12345
    url = 'url'
    repo_name = 'repo_name'
    analysis_urlsafe_key = 'urlsafe_key'
    culprit = FlakeCulprit.Create(repo_name, revision, commit_position)
    culprit.flake_analysis_urlsafe_keys = [analysis_urlsafe_key]
    culprit.url = url
    culprit.put()

    culprit = recursive_flake_try_job_pipeline.UpdateCulprit(
        analysis_urlsafe_key, revision, commit_position, repo_name)

    self.assertIsNotNone(culprit)
    self.assertEqual(1, len(culprit.flake_analysis_urlsafe_keys))
    self.assertIn(analysis_urlsafe_key, culprit.flake_analysis_urlsafe_keys)
    self.assertEqual(url, culprit.url)
    self.assertEqual(repo_name, culprit.repo_name)
    self.assertEqual(revision, culprit.revision)

  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog', return_value=None)
  def testUpdateCulpritNoLogs(self, _):
    revision = 'a1b2c3d4'
    commit_position = 12345
    repo_name = 'repo_name'
    analysis_urlsafe_key = 'urlsfe_key'
    culprit = recursive_flake_try_job_pipeline.UpdateCulprit(
        analysis_urlsafe_key, revision, commit_position, repo_name)

    self.assertIn(analysis_urlsafe_key, culprit.flake_analysis_urlsafe_keys)
    self.assertEqual(commit_position, culprit.commit_position)
    self.assertEqual(revision, culprit.revision)
    self.assertIsNone(culprit.url)
    self.assertEqual(repo_name, culprit.repo_name)

  def testGetTryJobNew(self):
    existing_try_job = FlakeTryJob.Create('m', 'b', 's', 't', 'a1b2c3d4')
    existing_try_job.put()
    self.assertEqual(existing_try_job,
                     recursive_flake_try_job_pipeline._GetTryJob(
                         'm', 'b', 's', 't', 'a1b2c3d4'))

  def testGetTryJobExisting(self):
    try_job = recursive_flake_try_job_pipeline._GetTryJob(
        'm', 'b', 's', 't', 'e5f6a1b2')
    self.assertIsNotNone(try_job)
    self.assertEqual(try_job.git_hash, 'e5f6a1b2')

  def testNeedANewTryJob(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    try_job = FlakeTryJob.Create('m', 'b', 's', 't', 'a1b2c3d4')
    self.assertTrue(
        recursive_flake_try_job_pipeline._NeedANewTryJob(
            analysis, try_job, 200, True))
    self.assertTrue(
        recursive_flake_try_job_pipeline._NeedANewTryJob(
            analysis, try_job, 200, False))

  def testNeedANewTryJobWithExistingFlakyTryJob(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = {
        'try_job_rerun': {
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98
        }
    }
    try_job = FlakeTryJob.Create('m', 'b', 's', 't', 'a1b2c3d4')
    try_job.flake_results = [{
        'report': {
            'result': {
                'a1b2c3d4': {
                    's': {
                        'pass_fail_counts': {
                            't': {
                                'pass_count': 60,
                                'fail_count': 40
                            }
                        }
                    }
                }
            }
        }
    }]
    self.assertFalse(
        recursive_flake_try_job_pipeline._NeedANewTryJob(
            analysis, try_job, 200, False))

  def testNeedANewTryJobWithExistingStableTryJobInsufficientIterations(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = {
        'try_job_rerun': {
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98
        }
    }
    try_job = FlakeTryJob.Create('m', 'b', 's', 't', 'a1b2c3d4')
    try_job.flake_results = [{
        'report': {
            'result': {
                'a1b2c3d4': {
                    's': {
                        'pass_fail_counts': {
                            't': {
                                'pass_count': 99,
                                'fail_count': 1
                            }
                        }
                    }
                }
            }
        }
    }]
    self.assertTrue(
        recursive_flake_try_job_pipeline._NeedANewTryJob(
            analysis, try_job, 200, False))

  def testNeedANewTryJobWithExistingStableTryJobSufficientIterations(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = {
        'try_job_rerun': {
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98
        }
    }
    try_job = FlakeTryJob.Create('m', 'b', 's', 't', 'a1b2c3d4')
    try_job.flake_results = [{
        'report': {
            'result': {
                'a1b2c3d4': {
                    's': {
                        'pass_fail_counts': {
                            't': {
                                'pass_count': 200,
                                'fail_count': 0
                            }
                        }
                    }
                }
            }
        }
    }]
    self.assertFalse(
        recursive_flake_try_job_pipeline._NeedANewTryJob(
            analysis, try_job, 200, False))

  def testNeedANewTryJobWithExistingTryJobNonexistentTest(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = {
        'try_job_rerun': {
            'lower_flake_threshold': 0.02,
            'upper_flake_threshold': 0.98
        }
    }
    try_job = FlakeTryJob.Create('m', 'b', 's', 't', 'a1b2c3d4')
    try_job.flake_results = [{'report': {'result': {'a1b2c3d4': {'s': {}}}}}]
    self.assertFalse(
        recursive_flake_try_job_pipeline._NeedANewTryJob(
            analysis, try_job, 200, False))

  def testSetAnalysisTryJobStatusRunning(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    recursive_flake_try_job_pipeline._SetAnalysisTryJobStatus(
        analysis, analysis_status.RUNNING)
    self.assertEqual(analysis.try_job_status, analysis_status.RUNNING)

  def testSetAnalysisTryJobStatusRunningAlreadyRunning(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.try_job_status = analysis_status.RUNNING
    recursive_flake_try_job_pipeline._SetAnalysisTryJobStatus(
        analysis, analysis_status.RUNNING)
    self.assertEqual(analysis.try_job_status, analysis_status.RUNNING)

  def testGetTryJobDataPointsNoTryJobsYet(self):
    suspected_flake_build_number = 12345
    suspected_flake_commit_position = 100,
    suspected_flake_lower_bound = 90
    data_points = [
        DataPoint.Create(
            pass_rate=0.8,
            commit_position=100,
            build_number=suspected_flake_build_number)
    ]
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = suspected_flake_build_number
    analysis.data_points = data_points

    normalized_data_points = _GetNormalizedTryJobDataPoints(
        analysis, suspected_flake_lower_bound, suspected_flake_commit_position)
    self.assertEqual(normalized_data_points[0].run_point_number, 100)
    self.assertEqual(normalized_data_points[0].pass_rate, 0.8)
    self.assertEqual(len(normalized_data_points), 1)

  def testGetTryJobDataPointsWithTryJobs(self):
    suspected_flake_build_number = 12345
    all_data_points = [
        DataPoint.Create(
            pass_rate=0.8,
            commit_position=100,
            build_number=suspected_flake_build_number),
        DataPoint.Create(
            pass_rate=1.0,
            commit_position=90,
            build_number=suspected_flake_build_number - 1),
        DataPoint.Create(pass_rate=0.8, commit_position=99, try_job_url='url')
    ]

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = suspected_flake_build_number
    analysis.data_points = all_data_points
    normalized_data_points = _GetNormalizedTryJobDataPoints(analysis, 91, 100)

    self.assertEqual(normalized_data_points[0].run_point_number, 99)
    self.assertEqual(normalized_data_points[0].pass_rate, 0.8)
    self.assertEqual(normalized_data_points[1].run_point_number, 100)
    self.assertEqual(normalized_data_points[1].pass_rate, 0.8)

  @mock.patch.object(
      RecursiveFlakeTryJobPipeline, 'was_aborted', return_value=True)
  def testRecursiveFlakeTryJobPipelineAborted(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    step_name = 's'
    test_name = 't'
    revision = 'rev'
    commit_position = 1
    build_id = 'b1'
    lower_bound_commit_position = 0

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.try_job_ids = [build_id]
    try_job.put()

    try_job_data = FlakeTryJobData.Create(build_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    rftp = RecursiveFlakeTryJobPipeline(
        analysis.key.urlsafe(),
        commit_position,
        revision,
        lower_bound_commit_position,
        100,
        None,
        _DEFAULT_CACHE_NAME,
        None,
        rerun=False)
    rftp._LogUnexpectedAbort()

    expected_error = {
        'error': 'RecursiveFlakeTryJobPipeline was aborted unexpectedly',
        'message': 'RecursiveFlakeTryJobPipeline was aborted unexpectedly'
    }

    self.assertEqual(analysis_status.ERROR, analysis.try_job_status)
    self.assertEqual(expected_error, analysis.error)
    self.assertEqual(analysis_status.ERROR, try_job.status)
    self.assertEqual(expected_error, try_job_data.error)

  @mock.patch.object(
      RecursiveFlakeTryJobPipeline, 'was_aborted', return_value=True)
  def testRecursiveFlakeTryJobPipelineAbortedNoUpdateCompletedTryJob(self, _):
    master_name = 'm'
    builder_name = 'b'
    master_build_number = 100
    suspected_build_commit_position = 1000
    step_name = 's'
    test_name = 't'
    revision = 'rev'
    commit_position = 1
    lower_bound_commit_position = 0

    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, master_build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.status = analysis_status.COMPLETED
    try_job.put()

    pipeline_job = RecursiveFlakeTryJobPipeline(
        analysis.key.urlsafe(), commit_position, revision,
        lower_bound_commit_position, suspected_build_commit_position, None,
        _DEFAULT_CACHE_NAME, None)

    pipeline_job._LogUnexpectedAbort()

    self.assertEqual(analysis_status.COMPLETED, try_job.status)

  def testCanStartTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    revision = 'rev'
    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    # Buildbot.
    with mock.patch(
        'waterfall.waterfall_config.GetWaterfallTrybot',
        return_value=('tryserver.chromium.linux', 'b_variable')):
      # Continue if the job is not to be run on swarmbucket.
      self.assertTrue(
          recursive_flake_try_job_pipeline._CanStartTryJob(try_job, False, 0))

    # LUCI.
    with mock.patch(
        'waterfall.waterfall_config.GetWaterfallTrybot',
        return_value=('luci.chromium.try', 'b_variable')):
      # Continue if re-run.
      self.assertTrue(
          recursive_flake_try_job_pipeline._CanStartTryJob(try_job, True, 0))
      # Continue if retry limit exceeded.
      self.assertTrue(
          recursive_flake_try_job_pipeline._CanStartTryJob(try_job, False, 100))
      with mock.patch(
          'waterfall.swarming_util.GetSwarmingBotCounts',
          return_value={'count': 10,
                        'available': 10}):
        # Continue if enough bots are available.
        self.assertTrue(
            recursive_flake_try_job_pipeline._CanStartTryJob(try_job, False, 0))
      with mock.patch(
          'waterfall.swarming_util.GetSwarmingBotCounts',
          return_value={'count': 10,
                        'available': 4}):
        # Delay the job if not enough bots are available.
        self.assertFalse(
            recursive_flake_try_job_pipeline._CanStartTryJob(try_job, False, 0))

  @mock.patch.object(recursive_flake_try_job_pipeline,
                     '_BASE_COUNT_DOWN_SECONDS', 0)
  @mock.patch.object(recursive_flake_try_job_pipeline, '_CanStartTryJob')
  def testTryLaterIfNoAvailableBots(self, mock_fn):
    mock_fn.side_effect = [False, True]
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    upper_bound_commit_position = 1000
    start_commit_position = 999
    revision = 'r999'
    try_job_id = 'try_job_id'
    lower_bound_commit_position = 998
    user_specified_iterations = None

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    iterations_to_rerun = analysis.algorithm_parameters.get(
        'try_job_rerun', {}).get('iterations_to_rerun')

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)

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
        expected_args=[
            master_name, builder_name, step_name, test_name, revision,
            analysis.key.urlsafe(), _DEFAULT_CACHE_NAME, None,
            iterations_to_rerun
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.MonitorTryJobPipeline,
        try_job_result,
        expected_args=[
            try_job.key.urlsafe(), failure_type.FLAKY_TEST, try_job_id
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.ProcessFlakeTryJobResultPipeline,
        None,
        expected_args=[
            revision, start_commit_position, try_job_result,
            try_job.key.urlsafe(),
            analysis.key.urlsafe()
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.NextCommitPositionPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(),
            try_job.key.urlsafe(), lower_bound_commit_position,
            upper_bound_commit_position, user_specified_iterations,
            _DEFAULT_CACHE_NAME, None, False
        ])

    pipeline_job = RecursiveFlakeTryJobPipeline(
        analysis.key.urlsafe(),
        start_commit_position,
        revision,
        lower_bound_commit_position,
        upper_bound_commit_position,
        None,
        _DEFAULT_CACHE_NAME,
        None,
        rerun=False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    self.assertIsNotNone(
        FlakeTryJob.Get(master_name, builder_name, step_name, test_name,
                        revision))
    self.assertEqual(analysis.last_attempted_revision, revision)
    self.assertIsNone(analysis.last_attempted_swarming_task_id)

  @mock.patch.object(recursive_flake_try_job_pipeline,
                     '_BASE_COUNT_DOWN_SECONDS', 0)
  @mock.patch.object(recursive_flake_try_job_pipeline, '_CanStartTryJob')
  def testOffPeakHours(self, mock_fn):
    mock_fn.side_effect = [False, True]
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    upper_bound_commit_position = 1000
    start_commit_position = 999
    revision = 'r999'
    try_job_id = 'try_job_id'
    lower_bound_commit_position = 998
    user_specified_iterations = None

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.status = analysis_status.COMPLETED
    analysis.algorithm_parameters = DEFAULT_CONFIG_DATA['check_flake_settings']
    analysis.Save()

    iterations_to_rerun = analysis.algorithm_parameters.get(
        'try_job_rerun', {}).get('iterations_to_rerun')

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)

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
        expected_args=[
            master_name, builder_name, step_name, test_name, revision,
            analysis.key.urlsafe(), _DEFAULT_CACHE_NAME, None,
            iterations_to_rerun
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.MonitorTryJobPipeline,
        try_job_result,
        expected_args=[
            try_job.key.urlsafe(), failure_type.FLAKY_TEST, try_job_id
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.ProcessFlakeTryJobResultPipeline,
        None,
        expected_args=[
            revision, start_commit_position, try_job_result,
            try_job.key.urlsafe(),
            analysis.key.urlsafe()
        ])
    self.MockPipeline(
        recursive_flake_try_job_pipeline.NextCommitPositionPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(),
            try_job.key.urlsafe(), lower_bound_commit_position,
            upper_bound_commit_position, user_specified_iterations,
            _DEFAULT_CACHE_NAME, None, False
        ])

    pipeline_job = RecursiveFlakeTryJobPipeline(
        analysis.key.urlsafe(),
        start_commit_position,
        revision,
        lower_bound_commit_position,
        upper_bound_commit_position,
        None,
        _DEFAULT_CACHE_NAME,
        None,
        rerun=False,
        retries=100)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    self.assertIsNotNone(
        FlakeTryJob.Get(master_name, builder_name, step_name, test_name,
                        revision))
    self.assertEqual(analysis.last_attempted_revision, revision)
    self.assertIsNone(analysis.last_attempted_swarming_task_id)

  @mock.patch.object(
      confidence, 'SteppinessForCommitPosition', return_value=0.6)
  def testGetSuspectedConmmitConfidenceScore(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 124, 's', 't')
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.7, commit_position=123)
    ]
    self.assertEqual(
        0.6,
        recursive_flake_try_job_pipeline._GetSuspectedCommitConfidenceScore(
            analysis, 123, analysis.data_points))
    self.assertIsNone(
        recursive_flake_try_job_pipeline._GetSuspectedCommitConfidenceScore(
            analysis, None, []))

  def testGetSuspectedCommitConfidenceScoreIntroducedNewFlakyTest(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 124, 's', 't')
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.7, commit_position=123),
        DataPoint.Create(
            pass_rate=flake_constants.PASS_RATE_TEST_NOT_FOUND,
            commit_position=122)
    ]
    self.assertEqual(
        1.0,
        recursive_flake_try_job_pipeline._GetSuspectedCommitConfidenceScore(
            analysis, 123, analysis.data_points))
