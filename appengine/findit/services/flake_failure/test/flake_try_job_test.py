# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import datetime
import mock

from common import exceptions
from gae_libs.pipelines import CreateInputObjectInstance
from gae_libs.testcase import TestCase
from libs.list_of_basestring import ListOfBasestring
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.run_flake_try_job_pipeline import (
    RunFlakeTryJobParameters)
from services import swarmed_test_util
from services import test_results
from services import try_job as try_job_service
from services.flake_failure import flake_try_job
from waterfall import waterfall_config
from waterfall.flake import flake_constants


class FlakeTryJobServiceTest(TestCase):

  def testGetSwarmingTaskIdForTryJobNoReport(self):
    self.assertIsNone(
        flake_try_job.GetSwarmingTaskIdForTryJob(None, None, None, None))

  def testIsTryJobResultAtRevisionValid(self):
    self.assertFalse(flake_try_job.IsTryJobResultAtRevisionValid(None, 'r'))
    self.assertFalse(flake_try_job.IsTryJobResultAtRevisionValid({}, 'r'))
    self.assertFalse(
        flake_try_job.IsTryJobResultAtRevisionValid({
            'report': {}
        }, 'r'))
    self.assertFalse(
        flake_try_job.IsTryJobResultAtRevisionValid({
            'report': {
                'result': {}
            }
        }, 'r'))
    self.assertTrue(
        flake_try_job.IsTryJobResultAtRevisionValid({
            'report': {
                'result': {
                    'r': {}
                }
            }
        }, 'r'))

  @mock.patch.object(swarmed_test_util, 'GetTestResultForSwarmingTask')
  def testGetSwarmingTaskIdForTryJobNotFoundTaskWithResult(self, mock_fn):
    output_json = {'per_iteration_data': [{}, {}]}
    mock_fn.return_result = output_json

    revision = 'r0'
    step_name = 'gl_tests'
    test_name = 'Test.One'
    report = {
        'result': {
            'r0': {
                'gl_tests': {
                    'status': 'passed',
                    'valid': True,
                    'pass_fail_counts': {
                        'Test.One': {
                            'pass_count': 100,
                            'fail_count': 0
                        }
                    },
                    'step_metadata': {
                        'swarm_task_ids': ['task1', 'task2']
                    }
                }
            }
        }
    }

    self.assertIsNone(
        flake_try_job.GetSwarmingTaskIdForTryJob(report, revision, step_name,
                                                 test_name))

  @mock.patch.object(
      swarmed_test_util, 'GetTestResultForSwarmingTask', return_value=None)
  def testGetSwarmingTaskIdForTryJobNoOutputJson(self, _):
    revision = 'r0'
    step_name = 'gl_tests'
    test_name = 'Test.One'
    report = {
        'result': {
            'r0': {
                'gl_tests': {
                    'status': 'passed',
                    'valid': True,
                    'pass_fail_counts': {
                        'Test.One': {
                            'pass_count': 100,
                            'fail_count': 0
                        }
                    },
                    'step_metadata': {
                        'swarm_task_ids': ['task1', 'task2']
                    }
                }
            }
        }
    }

    self.assertIsNone(
        flake_try_job.GetSwarmingTaskIdForTryJob(report, revision, step_name,
                                                 test_name))

  def testGetSwarmingTaskIdForTryJobOnlyOneTask(self):
    revision = 'r0'
    step_name = 'gl_tests'
    test_name = 'Test.One'
    report = {
        'result': {
            'r0': {
                'gl_tests': {
                    'status': 'passed',
                    'valid': True,
                    'pass_fail_counts': {
                        'Test.One': {
                            'pass_count': 100,
                            'fail_count': 0
                        }
                    },
                    'step_metadata': {
                        'swarm_task_ids': ['task1']
                    }
                }
            }
        }
    }

    self.assertEquals(
        flake_try_job.GetSwarmingTaskIdForTryJob(report, revision, step_name,
                                                 test_name), 'task1')

  def testGetSwarmingTaskIdForTryJobTestNotExist(self):
    revision = 'r0'
    step_name = 'gl_tests'
    test_name = 'Test.One'
    report = {
        'result': {
            'r0': {
                'gl_tests': {
                    'status': 'passed',
                    'valid': True,
                    'pass_fail_counts': {},
                    'step_metadata': {
                        'swarm_task_ids': ['task1', 'task2']
                    }
                }
            }
        }
    }

    self.assertEquals(
        flake_try_job.GetSwarmingTaskIdForTryJob(report, revision, step_name,
                                                 test_name), 'task1')

  def testIsTryJobResultAtRevisionValidForStep(self):
    self.assertTrue(
        flake_try_job.IsTryJobResultAtRevisionValidForStep({
            'browser_tests': {
                'valid': True
            }
        }, 'browser_tests'))
    self.assertFalse(
        flake_try_job.IsTryJobResultAtRevisionValidForStep(
            None, 'browser_tests'))
    self.assertFalse(
        flake_try_job.IsTryJobResultAtRevisionValidForStep({
            'browser_tests': {
                'valid': False
            }
        }, 'browser_tests'))
    self.assertFalse(
        flake_try_job.IsTryJobResultAtRevisionValidForStep({
            'some_tests': {
                'valid': True
            }
        }, 'wrong_tests'))

  @mock.patch.object(
      test_results, 'IsTestResultUseful', side_effect=[False, True])
  @mock.patch.object(swarmed_test_util, 'GetTestResultForSwarmingTask')
  def testGetSwarmingTaskIdForTryJob(self, mock_fn, _):
    output_json_1 = {'per_iteration_data': [{}, {}]}
    output_json_2 = {'per_iteration_data': [{'Test.One': 'log for Test.One'}]}
    mock_fn.side_effect = [output_json_1, output_json_2]

    revision = 'r0'
    step_name = 'gl_tests'
    test_name = 'Test.One'
    report = {
        'result': {
            'r0': {
                'gl_tests': {
                    'status': 'passed',
                    'valid': True,
                    'pass_fail_counts': {
                        'Test.One': {
                            'pass_count': 100,
                            'fail_count': 0
                        }
                    },
                    'step_metadata': {
                        'swarm_task_ids': ['task1', 'task2']
                    }
                }
            }
        }
    }

    task_id = flake_try_job.GetSwarmingTaskIdForTryJob(report, revision,
                                                       step_name, test_name)

    self.assertEquals('task2', task_id)

  def testGetPassFailCounts(self):
    self.assertEquals((0.9, 10),
                      flake_try_job._GetPassRateAndTries({
                          't': {
                              'pass_count': 9,
                              'fail_count': 1,
                          }
                      }, 't'))
    self.assertEquals((flake_constants.PASS_RATE_TEST_NOT_FOUND, 0),
                      flake_try_job._GetPassRateAndTries({}, 't'))

  def testUpdateDataPointsWithExistingDataPoint(self):
    commit_position = 1000
    revision = 'r1000'

    existing_data_points = [DataPoint.Create(commit_position=commit_position)]

    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's', 't')
    analysis.data_points = existing_data_points
    analysis.Save()

    try_job = FlakeTryJob.Create('m', 'b', 's', 't', revision)
    try_job.put()

    flake_try_job.UpdateAnalysisDataPointsWithTryJobResult(
        analysis, try_job, commit_position, revision)

    self.assertEqual(existing_data_points, analysis.data_points)

  @mock.patch.object(flake_try_job, 'GetSwarmingTaskIdForTryJob')
  def testUpdateAnalysisDataPointsWithTryJobResults(
      self, mocked_get_swarming_task_id):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'

    commit_position = 1000
    revision = 'r1000'
    try_job_id = 'try_job_id'
    task_id = 'swarming_task_id'

    mocked_get_swarming_task_id.return_value = task_id

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.try_job_ids = [try_job_id]
    try_job.flake_results = [{
        'report': {
            'result': {
                revision: {
                    step_name: {
                        'valid': True,
                        'pass_fail_counts': {
                            test_name: {
                                'pass_count': 99,
                                'fail_count': 1
                            }
                        }
                    }
                }
            }
        }
    }]
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.start_time = datetime(2017, 10, 17, 1, 0, 0)
    try_job_data.end_time = datetime(2017, 10, 17, 2, 0, 0)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    flake_try_job.UpdateAnalysisDataPointsWithTryJobResult(
        analysis, try_job, commit_position, revision)

    expected_data_points = [
        DataPoint.Create(
            commit_position=commit_position,
            git_hash=revision,
            iterations=100,
            elapsed_seconds=3600,
            task_ids=[task_id],
            pass_rate=0.99)
    ]

    self.assertEqual(expected_data_points, analysis.data_points)

  def testGetBuildProperties(self):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    git_hash = 'a1b2c3d4'
    iterations = 200

    expected_properties = {
        'recipe': 'findit/chromium/flake',
        'skip_tests': False,
        'target_mastername': master_name,
        'target_testername': builder_name,
        'test_revision': git_hash,
        'test_repeat_count': 200,
        'tests': {
            step_name: [test_name]
        },
    }

    properties = flake_try_job.GetBuildProperties(
        master_name, builder_name, step_name, test_name, git_hash, iterations)

    self.assertEqual(properties, expected_properties)

  def testCreateTryJobData(self):
    try_job = FlakeTryJob.Create('m', 'b', 's1', 't1', 'hash')
    try_job.put()
    analysis = MasterFlakeAnalysis.Create('m', 'b', 123, 's1', 't1')
    analysis.put()
    build_id = 'build_id'
    pipeline_id = 'pipeline_id'
    flake_try_job.CreateTryJobData(build_id, try_job.key,
                                   analysis.key.urlsafe(), pipeline_id)
    try_job_data = FlakeTryJobData.Get(build_id)
    self.assertIsNotNone(try_job_data)

  def testUpdateTryJob(self):
    FlakeTryJob.Create('m', 'b', 's1', 't1', 'hash').put()
    build_id = 'build_id'
    try_job = flake_try_job.UpdateTryJob('m', 'b', 's1', 't1', 'hash', build_id)
    self.assertEqual(try_job.try_job_ids[0], build_id)

  @mock.patch.object(
      waterfall_config, 'GetFlakeTrybot', return_value=('m', 'b'))
  @mock.patch.object(flake_try_job, 'GetBuildProperties', return_value={})
  @mock.patch.object(
      try_job_service, 'TriggerTryJob', return_value=('id', None))
  def testScheduleFlakeTryJobSuccess(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    revision = 'r1000'
    expected_try_job_id = 'id'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

    parameters = CreateInputObjectInstance(
        RunFlakeTryJobParameters,
        analysis_urlsafe_key=analysis.key.urlsafe(),
        revision=revision,
        flake_cache_name=None,
        dimensions=ListOfBasestring(),
        urlsafe_try_job_key=try_job.key.urlsafe())

    try_job_id = flake_try_job.ScheduleFlakeTryJob(parameters, 'pipeline')

    try_job = FlakeTryJob.Get(master_name, builder_name, step_name, test_name,
                              revision)
    try_job_data = FlakeTryJobData.Get(expected_try_job_id)

    expected_try_job_id = 'id'
    self.assertEqual(expected_try_job_id, try_job_id)
    self.assertEqual(expected_try_job_id,
                     try_job.flake_results[-1]['try_job_id'])
    self.assertTrue(expected_try_job_id in try_job.try_job_ids)
    self.assertIsNotNone(try_job_data)
    self.assertEqual(try_job_data.master_name, master_name)
    self.assertEqual(try_job_data.builder_name, builder_name)

  class MockedError(object):

    def __init__(self, message, reason):
      self.message = message
      self.reason = reason

  @mock.patch.object(
      waterfall_config, 'GetFlakeTrybot', return_value=('m', 'b'))
  @mock.patch.object(flake_try_job, 'GetBuildProperties', return_value={})
  @mock.patch.object(
      try_job_service,
      'TriggerTryJob',
      return_value=(None, MockedError('message', 'reason')))
  def testScheduleFlakeTryJobRaise(self, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    revision = 'r1000'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

    parameters = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        revision=revision,
        flake_cache_name=None,
        dimensions=ListOfBasestring())

    with self.assertRaises(exceptions.RetryException):
      flake_try_job.ScheduleFlakeTryJob(parameters, 'pipeline')

  def testGetTryJobExistingTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    revision = 'r1000'

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, revision)
    try_job.put()

    retrieved_try_job = flake_try_job.GetTryJob(master_name, builder_name,
                                                step_name, test_name, revision)
    self.assertEqual(retrieved_try_job, try_job)

  def testGetTryJobNewTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    revision = 'r1000'

    self.assertIsNotNone(
        flake_try_job.GetTryJob(master_name, builder_name, step_name, test_name,
                                revision))
