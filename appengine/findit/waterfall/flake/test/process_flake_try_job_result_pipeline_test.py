# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from gae_libs.testcase import TestCase
from model.flake.flake_try_job import FlakeTryJob
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import swarming_util
from waterfall.flake import process_flake_try_job_result_pipeline
from waterfall.flake.process_flake_try_job_result_pipeline import (
    ProcessFlakeTryJobResultPipeline)


class ProcessFlakeTryJobResultPipelineTest(TestCase):

  def testProcessFlakeTryJobResultPipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    revision = 'r4'
    commit_position = 4
    try_job_id = 'try_job_id'
    url = 'url'
    try_job_result = {
        'report': {
            'result': {
                revision: {
                    step_name: {
                        'status': 'failed',
                        'failures': [test_name],
                        'valid': True,
                        'pass_fail_counts': {
                            test_name: {
                                'pass_count': 20,
                                'fail_count': 80
                            }
                        }
                    }
                }
            }
        }
    }
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.Save()
    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)
    try_job.flake_results = [{
        'url': url,
        'report': try_job_result,
        'try_job_id': try_job_id
    }]
    try_job.try_job_ids = [try_job_id]
    try_job.put()
    ProcessFlakeTryJobResultPipeline().run(
        revision, commit_position, try_job_result, try_job.key.urlsafe(),
        analysis.key.urlsafe())
    resulting_data_point = analysis.data_points[-1]
    self.assertEqual(0.2, resulting_data_point.pass_rate)
    self.assertEqual(commit_position, resulting_data_point.commit_position)
    self.assertEqual(url, resulting_data_point.try_job_url)

  def testProcessFlakeTryJobResultPipelineTestDoesNotExist(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 100
    step_name = 's'
    test_name = 't'
    revision = 'r4'
    commit_position = 4
    try_job_id = 'try_job_id'
    url = 'url'
    try_job_result = {
        'report': {
            'result': {
                revision: {
                    step_name: {
                        'status': 'skipped',
                        'valid': True
                    }
                }
            }
        }
    }
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.Save()
    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, revision)
    try_job.flake_results = [{
        'url': url,
        'report': try_job_result,
        'try_job_id': try_job_id
    }]
    try_job.try_job_ids = [try_job_id]
    try_job.put()
    ProcessFlakeTryJobResultPipeline().run(
        revision, commit_position, try_job_result, try_job.key.urlsafe(),
        analysis.key.urlsafe())
    resulting_data_point = analysis.data_points[-1]
    self.assertEqual(-1, resulting_data_point.pass_rate)
    self.assertEqual(commit_position, resulting_data_point.commit_position)
    self.assertEqual(url, resulting_data_point.try_job_url)

  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask')
  def testGetSwarmingTaskIdForTryJob(self, mock_fn):
    output_json_1 = {
        'per_iteration_data': [{}, {}]
    }
    output_json_2 = {
        'per_iteration_data': [
            {
                'Test.One': 'log for Test.One'
            }
        ]
    }
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

    task_id = process_flake_try_job_result_pipeline._GetSwarmingTaskIdForTryJob(
        report, revision, step_name, test_name)
    self.assertEquals( 'task2', task_id)

  def testGetSwarmingTaskIdForTryJobNoReport(self):
    self.assertIsNone(
        process_flake_try_job_result_pipeline._GetSwarmingTaskIdForTryJob(
            None, None, None, None))

  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask')
  def testGetSwarmingTaskIdForTryJobNotFoundTaskWithResult(self, mock_fn):
    output_json = {
        'per_iteration_data': [{}, {}]
    }
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
        process_flake_try_job_result_pipeline._GetSwarmingTaskIdForTryJob(
            report, revision, step_name, test_name))

  @mock.patch.object(swarming_util, 'GetIsolatedOutputForTask',
                     return_value=None)
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
      process_flake_try_job_result_pipeline._GetSwarmingTaskIdForTryJob(
        report, revision, step_name, test_name))

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
      process_flake_try_job_result_pipeline._GetSwarmingTaskIdForTryJob(
        report, revision, step_name, test_name), 'task1')

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
              'swarm_task_ids': ['task1']
            }
          }
        }
      }
    }

    self.assertEquals(
      process_flake_try_job_result_pipeline._GetSwarmingTaskIdForTryJob(
        report, revision, step_name, test_name), 'task1')
