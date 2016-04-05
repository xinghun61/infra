# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from common import buildbucket_client
from common.git_repository import GitRepository
from model.wf_try_job import WfTryJob
from pipeline_wrapper import pipeline_handlers
from waterfall import swarming_util
from waterfall import trigger_swarming_task_pipeline
from waterfall.swarming_task_request import SwarmingTaskRequest
from waterfall.swarming_tasks_to_try_job_pipeline import (
    SwarmingTasksToTryJobPipeline)
from waterfall.test import wf_testcase
from waterfall.try_job_type import TryJobType


_ISOLATED_SERVER = 'https://isolateserver.appspot.com'
_ISOLATED_STORAGE_URL = 'isolateserver.storage.googleapis.com'
_SAMPLE_FAILURE_LOG = {
    'per_iteration_data': [
        {
            'TestSuite1.test1': [
                {
                    'status': 'SUCCESS',
                    'other_info': 'N/A'
                }
            ],
            'TestSuite1.test2': [
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                },
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                },
                {
                    'status': 'SUCCESS',
                    'other_info': 'N/A'
                }
            ],
            'TestSuite1.test3': [
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                },
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                },
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                }
            ]
        },
        {
            'TestSuite1.test1': [
                {
                    'status': 'SUCCESS',
                    'other_info': 'N/A'
                }
            ],
            'TestSuite1.test2': [
                {
                    'status': 'SUCCESS',
                    'other_info': 'N/A'
                }
            ],
            'TestSuite1.test3': [
                {
                    'status': 'FAILURE',
                    'other_info': 'N/A'
                }
            ]
        }
    ]
}


class SwarmingTasksToTryJobPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def _MockTriggerTryJobs(self, responses):
    def MockedTriggerTryJobs(*_):
      try_job_results = []
      for response in responses:
        if response.get('error'):  # pragma: no cover
          try_job_results.append((
              buildbucket_client.BuildbucketError(response['error']), None))
        else:
          try_job_results.append((
              None, buildbucket_client.BuildbucketBuild(response['build'])))
      return try_job_results
    self.mock(buildbucket_client, 'TriggerTryJobs', MockedTriggerTryJobs)

  def _MockGetTryJobs(self, build_id):
    def MockedGetTryJobs(*_):
      data = {
          '1': {
              'build': {
                  'id': '1',
                  'url': 'url',
                  'status': 'COMPLETED',
                  'result_details_json': json.dumps({
                      'properties': {
                          'report': {
                              'result': {
                                  'rev1': 'passed',
                                  'rev2': 'failed'
                              },
                              'metadata': {
                                  'regression_range_size': 2
                              }
                          }
                      }
                  })
              }
          },
          '2': {
              'build': {
                  'id': '2',
                  'url': 'url',
                  'status': 'COMPLETED',
                  'result_details_json': json.dumps({
                      'properties': {
                          'report': {
                              'result': {
                                  'rev1': {
                                      'a_test': {
                                          'status': 'failed',
                                          'valid': True,
                                          'failures': ['TestSuite1.test3']
                                      },
                                      'b_test': {
                                          'status': 'passed',
                                          'valid': True,
                                          'failures': [],
                                      },
                                  }
                              },
                              'metadata': {
                                  'regression_range_size': 2
                              }
                          }
                      }
                  })
              }
          },
          '3': {
              'error': {
                  'reason': 'BUILD_NOT_FOUND',
                  'message': 'message',
              }
          }
      }
      try_job_results = []
      build_error = data.get(build_id)
      if build_error.get('error'):  # pragma: no cover
        try_job_results.append((
            buildbucket_client.BuildbucketError(build_error['error']), None))
      else:
        try_job_results.append((
            None, buildbucket_client.BuildbucketBuild(build_error['build'])))
      return try_job_results
    self.mock(buildbucket_client, 'GetTryJobs', MockedGetTryJobs)

  def _MockGetChangeLog(self, revision):
    def MockedGetChangeLog(*_):
      class MockedChangeLog(object):

        def __init__(self, commit_position, code_review_url):
          self.commit_position = commit_position
          self.code_review_url = code_review_url

      mock_change_logs = {}
      mock_change_logs['rev1'] = MockedChangeLog('1', 'url_1')
      mock_change_logs['rev2'] = MockedChangeLog('2', 'url_2')
      return mock_change_logs.get(revision)
    self.mock(GitRepository, 'GetChangeLog', MockedGetChangeLog)

  def testSuccessfullyScheduleNewTryJobForCompile(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    responses = [
        {
            'build': {
                'id': '1',
                'url': 'url',
                'status': 'SCHEDULED',
            }
        }
    ]
    self._MockTriggerTryJobs(responses)
    self._MockGetTryJobs('1')
    self._MockGetChangeLog('rev2')

    WfTryJob.Create(master_name, builder_name, build_number).put()

    root_pipeline = SwarmingTasksToTryJobPipeline(
        master_name, builder_name, build_number, 'rev1', 'rev2', ['rev2'],
        TryJobType.COMPILE)
    root_pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    expected_try_job_results = [
        {
            'report': {
                'result': {
                    'rev1': 'passed',
                    'rev2': 'failed'
                },
                'metadata': {
                    'regression_range_size': 2
                }
            },
            'url': 'url',
            'try_job_id': '1',
            'culprit': {
                'compile': {
                    'revision': 'rev2',
                    'commit_position': '2',
                    'review_url': 'url_2'
                }
            }
        }
    ]
    self.assertEqual(expected_try_job_results, try_job.compile_results)

  def testSuccessfullyScheduleNewTryJobForTest(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    targeted_tests = {
        'a_test': ['TestSuite1.test1', 'TestSuite1.test3'],
        'b_test': [],  # Non-swarming test.
    }

    # Mocks for TriggerSwarmingTaskPipeline.
    def MockedDownloadSwarmingTaskData(*_):
      return [{'task_id': '1'}, {'task_id': '2'}]
    self.mock(swarming_util, 'ListSwarmingTasksDataByTags',
              MockedDownloadSwarmingTaskData)

    def MockedGetSwarmingTaskRequest(ref_task_id, *_):
      self.assertEqual('1', ref_task_id)
      return SwarmingTaskRequest.Deserialize({
          'expiration_secs': 3600,
          'name': 'ref_task_request',
          'parent_task_id': 'pti',
          'priority': 25,
          'properties': {
              'command': 'cmd',
              'dimensions': [{'key': 'k', 'value': 'v'}],
              'env': [
                  {'key': 'a', 'value': '1'},
                  {'key': 'GTEST_SHARD_INDEX', 'value': '1'},
                  {'key': 'GTEST_TOTAL_SHARDS', 'value': '5'},
              ],
              'execution_timeout_secs': 3600,
              'extra_args': ['--flag=value', '--gtest_filter=d.f'],
              'grace_period_secs': 30,
              'idempotent': True,
              'inputs_ref': {'a': 1},
              'io_timeout_secs': 1200,
          },
          'tags': ['master:a', 'buildername:b'],
          'user': 'user',
      })
    self.mock(swarming_util, 'GetSwarmingTaskRequest',
              MockedGetSwarmingTaskRequest)

    new_request_json = {}
    def MockedTriggerSwarmingTask(new_request, *_):
      self.assertEqual({}, new_request_json)
      new_request_json.update(new_request.Serialize())
      return 'task_id1'
    self.mock(swarming_util, 'TriggerSwarmingTask', MockedTriggerSwarmingTask)

    def MockedGetSwarmingTaskName(*_):
      return 'new_task_name'
    self.mock(trigger_swarming_task_pipeline, '_GetSwarmingTaskName',
              MockedGetSwarmingTaskName)

    # Mocks for ProcessSwarmingTaskResultPipeline.
    def MockedGetSwarmingTaskResultById(task_id, _):
      swarming_task_results = {
          'task_id1': {
              'state': 'COMPLETED',
              'outputs_ref': {
                  'isolatedserver': _ISOLATED_SERVER,
                  'namespace': 'default-gzip',
                  'isolated': 'shard1_isolated'
              }
          }
      }
      mocked_result = swarming_task_results.get(task_id)
      return mocked_result
    self.mock(swarming_util, 'GetSwarmingTaskResultById',
              MockedGetSwarmingTaskResultById)

    def MockedGetSwarmingTaskFailureLog(*_):
      return _SAMPLE_FAILURE_LOG
    self.mock(swarming_util, 'GetSwarmingTaskFailureLog',
              MockedGetSwarmingTaskFailureLog)

    # Mocks for try job pipelines.
    responses = [
        {
            'build': {
                'id': '2',
                'url': 'url',
                'status': 'SCHEDULED',
            }
        }
    ]
    self._MockTriggerTryJobs(responses)
    self._MockGetTryJobs('2')
    self._MockGetChangeLog('rev1')

    WfTryJob.Create(master_name, builder_name, build_number).put()

    root_pipeline = SwarmingTasksToTryJobPipeline(
        master_name, builder_name, build_number, 'rev0', 'rev1', ['rev1'],
        TryJobType.TEST, None, targeted_tests)
    root_pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    expected_try_job_results = [
        {
            'report': {
                'result': {
                    'rev1': {
                        'a_test': {
                            'status': 'failed',
                            'valid': True,
                            'failures': ['TestSuite1.test3']
                        },
                        'b_test': {
                            'status': 'passed',
                            'valid': True,
                            'failures': [],
                        },
                    }
                },
                'metadata': {
                    'regression_range_size': 2
                }
            },
            'url': 'url',
            'try_job_id': '2',
            'culprit': {
                'a_test': {
                    'tests': {
                        'TestSuite1.test3': {
                            'revision': 'rev1',
                            'commit_position': '1',
                            'review_url': 'url_1'
                        }
                    }
                }
            }
        }
    ]

    self.assertEqual(expected_try_job_results, try_job.test_results)
