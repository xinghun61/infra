# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from common import constants
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from model.flake.flake_culprit import FlakeCulprit
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import build_util
from waterfall import swarming_util
from waterfall.flake import confidence
from waterfall.flake import initialize_flake_try_job_pipeline
from waterfall.flake import recursive_flake_try_job_pipeline
from waterfall.flake.initialize_flake_try_job_pipeline import (
    InitializeFlakeTryJobPipeline)
from waterfall.flake.recursive_flake_try_job_pipeline import (
    RecursiveFlakeTryJobPipeline)
from waterfall.flake.send_notification_for_flake_culprit_pipeline import (
    SendNotificationForFlakeCulpritPipeline)
from waterfall.test import wf_testcase

_DEFAULT_CACHE_NAME = swarming_util.GetCacheName('pm', 'pb')


class MockInfo(object):

  def __init__(self):
    self.parent_mastername = 'pm'
    self.parent_buildername = 'pb'


class InitializeFlakeTryJobPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testHasSufficientConfidenceToRunTryJobs(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = {
        'minimum_confidence_score_to_run_tryjobs': 0.6
    }
    analysis.confidence_in_suspected_build = 0.7
    self.assertTrue(
        initialize_flake_try_job_pipeline._HasSufficientConfidenceToRunTryJobs(
            analysis))

  def testInsufficientConfidenceToRunTryJobs(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.algorithm_parameters = {
        'minimum_confidence_score_to_run_tryjobs': 0.6
    }
    analysis.confidence_in_suspected_build = 0.5
    self.assertFalse(
        initialize_flake_try_job_pipeline._HasSufficientConfidenceToRunTryJobs(
            analysis))

  def testGetFullBlamedCLsAndLowerBoundForBisectMultipleInvalidPoints(self):
    data_points = [
        DataPoint.Create(
            pass_rate=0.9,
            build_number=100,
            commit_position=1000,
            blame_list=['r1000', 'r999'],
            previous_build_commit_position=998),
        DataPoint.Create(
            pass_rate=-1,
            build_number=99,
            blame_list=['r998'],
            has_valid_artifact=False,
            commit_position=998,
            previous_build_commit_position=997),
        DataPoint.Create(
            pass_rate=1.0,
            build_number=98,
            commit_position=997,
            blame_list=['r997', 'r996'],
            previous_build_commit_position=995),
        DataPoint.Create(
            pass_rate=-1,
            build_number=95,
            blame_list=['r995'],
            has_valid_artifact=False,
            commit_position=995,
            previous_build_commit_position=990)
    ]
    suspected_point = data_points[0]
    self.assertEqual(
        ({
            998: 'r998',
            999: 'r1000',
            1000: 'r999'
        }, 997),
        initialize_flake_try_job_pipeline._GetFullBlamedCLsAndLowerBound(
            suspected_point, data_points))

  def testGetFullBlamedCLsAndLowerBound(self):
    data_points = [
        DataPoint.Create(
            pass_rate=0.9,
            build_number=100,
            commit_position=1000,
            blame_list=['r1000', 'r999'],
            previous_build_commit_position=998),
        DataPoint.Create(
            pass_rate=-1,
            build_number=99,
            blame_list=['r998'],
            has_valid_artifact=False,
            commit_position=998,
            previous_build_commit_position=997)
    ]
    suspected_point = data_points[0]
    self.assertEqual(
        ({
            998: 'r998',
            999: 'r1000',
            1000: 'r999'
        }, 997),
        initialize_flake_try_job_pipeline._GetFullBlamedCLsAndLowerBound(
            suspected_point, data_points))

  def testGetFullBlamedCLsAndLowerBoundAllValidPoints(self):
    data_points = [
        DataPoint.Create(
            pass_rate=0.9,
            build_number=100,
            commit_position=1000,
            blame_list=['r1000', 'r999'],
            previous_build_commit_position=998),
        DataPoint.Create(
            pass_rate=-1,
            build_number=99,
            blame_list=['r998'],
            commit_position=998,
            previous_build_commit_position=997),
        DataPoint.Create(
            pass_rate=1.0,
            build_number=98,
            commit_position=997,
            blame_list=['r997', 'r996'],
            previous_build_commit_position=995)
    ]
    suspected_point = data_points[0]
    self.assertEqual(
        ({
            999: 'r1000',
            1000: 'r999'
        }, 998),
        initialize_flake_try_job_pipeline._GetFullBlamedCLsAndLowerBound(
            suspected_point, data_points))

  def testDataPointBeforeSuspectedIsFullyStable(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 100
    analysis.data_points = [
        DataPoint.Create(pass_rate=1.0, build_number=99),
        DataPoint.Create(pass_rate=1.0, build_number=100)
    ]
    self.assertTrue(
        initialize_flake_try_job_pipeline._DataPointBeforeSuspectIsFullyStable(
            analysis))

  def testDataPointBeforeSuspectedIsNotFullyStable(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 100
    analysis.data_points = [
        DataPoint.Create(pass_rate=0.99, build_number=99),
        DataPoint.Create(pass_rate=0.97, build_number=100)
    ]
    self.assertFalse(
        initialize_flake_try_job_pipeline._DataPointBeforeSuspectIsFullyStable(
            analysis))

  def testShouldRunTryJobsNoSuspectedBuild(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    self.assertFalse(
        initialize_flake_try_job_pipeline._ShouldRunTryJobs(analysis, True))
    self.assertFalse(
        initialize_flake_try_job_pipeline._ShouldRunTryJobs(analysis, False))

  def testShouldRunTryJobsUserSpecifiedRange(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 100
    self.assertTrue(
        initialize_flake_try_job_pipeline._ShouldRunTryJobs(analysis, True))

  @mock.patch.object(
      initialize_flake_try_job_pipeline,
      '_DataPointBeforeSuspectIsFullyStable',
      return_value=False)
  def testShouldRunTryJobsPreviousDataPointNotStable(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 100
    self.assertFalse(
        initialize_flake_try_job_pipeline._ShouldRunTryJobs(analysis, False))

  @mock.patch.object(
      initialize_flake_try_job_pipeline,
      '_DataPointBeforeSuspectIsFullyStable',
      return_value=True)
  @mock.patch.object(
      initialize_flake_try_job_pipeline,
      '_HasSufficientConfidenceToRunTryJobs',
      return_value=False)
  def testShouldRunTryJobsPreviousDataPointInsufficientConfidence(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 100
    self.assertFalse(
        initialize_flake_try_job_pipeline._ShouldRunTryJobs(analysis, False))

  @mock.patch.object(
      initialize_flake_try_job_pipeline,
      '_DataPointBeforeSuspectIsFullyStable',
      return_value=True)
  @mock.patch.object(
      initialize_flake_try_job_pipeline,
      '_HasSufficientConfidenceToRunTryJobs',
      return_value=True)
  def testShouldRunTryJobsPreviousDataPointSufficientConfidence(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 100
    self.assertTrue(
        initialize_flake_try_job_pipeline._ShouldRunTryJobs(analysis, False))

  def testRevisionToCommitPositions(self):
    self.assertEqual(
        {
            'a': 1,
            'b': 2
        },
        initialize_flake_try_job_pipeline._RevisionToCommitPositions({
            1: 'a',
            2: 'b'
        }))

  def testInitializeFlakeTryJopPipelineNoSuspectedBuild(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.start_time = datetime(2016, 6, 26, 23)
    analysis.Save()

    self.MockPipeline(
        RecursiveFlakeTryJobPipeline, '', expected_args=[], expected_kwargs={})

    pipeline_job = InitializeFlakeTryJobPipeline(analysis.key.urlsafe(), [],
                                                 None, False, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      initialize_flake_try_job_pipeline,
      '_HasSufficientConfidenceToRunTryJobs',
      return_value=False)
  def testInitializeFlakeTryJopPipelineInsufficientConfidence(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.start_time = datetime(2016, 6, 26, 23)
    analysis.confidence_in_suspected_build = 0.7
    analysis.Save()

    self.MockPipeline(
        RecursiveFlakeTryJobPipeline, '', expected_args=[], expected_kwargs={})

    pipeline_job = InitializeFlakeTryJobPipeline(analysis.key.urlsafe(), [],
                                                 None, False, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

  @mock.patch.object(
      initialize_flake_try_job_pipeline, '_ShouldRunTryJobs', return_value=True)
  def testInitializeFlakeTryJopPipelineNoBlamelist(self, _):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.start_time = datetime(2016, 6, 26, 23)
    analysis.suspected_flake_build_number = 100
    analysis.confidence_in_suspected_build = 0.7
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=0.8,
            build_number=100,
            commit_position=1000,
            previous_build_commit_position=990,
            blame_list=[])
    ]
    analysis.Save()

    self.MockPipeline(
        RecursiveFlakeTryJobPipeline, '', expected_args=[], expected_kwargs={})

    pipeline_job = InitializeFlakeTryJobPipeline(analysis.key.urlsafe(), [],
                                                 None, False, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    self.assertIsNotNone(analysis.error)

  @mock.patch.object(recursive_flake_try_job_pipeline, 'UpdateCulprit')
  @mock.patch.object(MasterFlakeAnalysis, 'Update')
  @mock.patch.object(initialize_flake_try_job_pipeline, '_ShouldRunTryJobs')
  def testInitializeFlakeTryJopPipelineSingleCommit(
      self, mocked_run_try_jobs, mocked_update_analysis, mocked_update_culprit):
    mocked_run_try_jobs.return_value = True
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 100
    analysis.confidence_in_suspected_build = 0.7
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=0.8,
            build_number=100,
            commit_position=1000,
            previous_build_commit_position=999,
            blame_list=['r1000'])
    ]
    analysis.Save()

    expected_culprit = FlakeCulprit.Create('cr', 'r1', 1000, 'http://')
    expected_culprit.flake_analysis_urlsafe_keys.append(analysis.key.urlsafe())

    self.MockPipeline(
        RecursiveFlakeTryJobPipeline, '', expected_args=[], expected_kwargs={})
    self.MockPipeline(
        SendNotificationForFlakeCulpritPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline_job = InitializeFlakeTryJobPipeline(analysis.key.urlsafe(), [],
                                                 None, False, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()

    mocked_update_culprit.assert_called_once()
    mocked_update_analysis.assert_called_once()

  @mock.patch.object(build_util, 'GetBuildInfo', return_value=MockInfo())
  @mock.patch.object(
      initialize_flake_try_job_pipeline, '_ShouldRunTryJobs', return_value=True)
  def testInitializeFlakeTryJobPipelineRunTryJobs(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 100
    analysis.confidence_in_suspected_build = 0.7
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=0.8,
            build_number=100,
            commit_position=1000,
            previous_build_commit_position=995,
            blame_list=['r996', 'r997', 'r998', 'r999', 'r1000'])
    ]
    analysis.Save()

    self.MockPipeline(
        RecursiveFlakeTryJobPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), [], 997, 'r997', 995, 1000, None,
            _DEFAULT_CACHE_NAME, None, False
        ],
        expected_kwargs={'retries': 0})
    self.MockPipeline(
        SendNotificationForFlakeCulpritPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline_job = InitializeFlakeTryJobPipeline(analysis.key.urlsafe(), [],
                                                 None, False, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    self.assertEqual(analysis_status.RUNNING, analysis.try_job_status)

  @mock.patch.object(
      initialize_flake_try_job_pipeline,
      '_ShouldRunTryJobs',
      return_value=False)
  def testInitializeFlakeTryJobPipelineBailOutOfTryJobs(self, *_):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.start_time = datetime(2016, 6, 26, 23)
    analysis.suspected_flake_build_number = 100
    analysis.confidence_in_suspected_build = 0.7
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=0.8,
            build_number=100,
            commit_position=1000,
            previous_build_commit_position=995,
            blame_list=['r996', 'r997', 'r998', 'r999', 'r1000'])
    ]
    analysis.Save()

    self.MockPipeline(
        RecursiveFlakeTryJobPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), [], 997, 'r997', 995, 1000, None,
            _DEFAULT_CACHE_NAME, None, False
        ],
        expected_kwargs={'retries': 0})
    self.MockPipeline(
        SendNotificationForFlakeCulpritPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline_job = InitializeFlakeTryJobPipeline(analysis.key.urlsafe(), [],
                                                 None, False, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    self.assertEqual(analysis_status.SKIPPED, analysis.try_job_status)

  @mock.patch.object(
      initialize_flake_try_job_pipeline, '_ShouldRunTryJobs', return_value=True)
  @mock.patch.object(build_util, 'GetBuildInfo', return_value=MockInfo())
  def testInitializeFlakeTryJobPipelineRunTryJobsWithHeuristicResults(self, *_):
    suspected_ranges = [('r996', 'r997')]
    expected_remaining_commits = [997]
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.suspected_flake_build_number = 100
    analysis.confidence_in_suspected_build = 0.7
    analysis.data_points = [
        DataPoint.Create(
            pass_rate=0.8,
            build_number=100,
            commit_position=1000,
            previous_build_commit_position=995,
            blame_list=['r996', 'r997', 'r998', 'r999', 'r1000'])
    ]
    analysis.Save()

    self.MockPipeline(
        RecursiveFlakeTryJobPipeline,
        '',
        expected_args=[
            analysis.key.urlsafe(), expected_remaining_commits, 996, 'r996',
            995, 1000, None, _DEFAULT_CACHE_NAME, None, False
        ],
        expected_kwargs={'retries': 0})
    self.MockPipeline(
        SendNotificationForFlakeCulpritPipeline,
        '',
        expected_args=[analysis.key.urlsafe()],
        expected_kwargs={})

    pipeline_job = InitializeFlakeTryJobPipeline(
        analysis.key.urlsafe(), suspected_ranges, None, False, False)
    pipeline_job.start(queue_name=constants.DEFAULT_QUEUE)
    self.execute_queued_tasks()
    self.assertEqual(analysis_status.RUNNING, analysis.try_job_status)
