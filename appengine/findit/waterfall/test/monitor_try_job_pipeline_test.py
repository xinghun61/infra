# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import logging
import mock
import time

from google.appengine.api import taskqueue

from common import exceptions
from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from gae_libs.pipelines import pipeline
from libs import analysis_status
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from services import try_job as try_job_service
from waterfall import swarming_util
from waterfall import monitor_try_job_pipeline
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline
from waterfall.test import wf_testcase


class MonitorTryJobPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(swarming_util, 'GetStepLog')
  @mock.patch.object(monitor_try_job_pipeline, 'buildbucket_client')
  def testGetTryJobsForCompileSuccessSerializedCallback(self, mock_buildbucket,
                                                        mock_report):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    regression_range_size = 2

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = (
        'https://build.chromium.org/p/m/builders/b/builds/1234')
    try_job_data.put()
    try_job.compile_results = [{
        'report': None,
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '1',
    }]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    build_response = {
        'id': '1',
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367574000000',
    }
    report = {
        'result': {
            'rev1': 'passed',
            'rev2': 'failed'
        },
        'metadata': {
            'regression_range_size': 2
        }
    }
    mock_buildbucket.GetTryJobs.return_value = [
        (None, buildbucket_client.BuildbucketBuild(build_response))
    ]
    mock_report.return_value = report

    monitor_pipeline = MonitorTryJobPipeline()
    monitor_pipeline.start_test()
    monitor_pipeline.run(try_job.key.urlsafe(), failure_type.COMPILE,
                         try_job_id)
    monitor_pipeline.callback(
        callback_params=json.dumps(monitor_pipeline.last_params))

    # Reload from ID to get all internal properties in sync.
    monitor_pipeline = MonitorTryJobPipeline.from_id(
        monitor_pipeline.pipeline_id)
    monitor_pipeline.finalized()
    compile_result = monitor_pipeline.outputs.default.value

    expected_compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            },
            'metadata': {
                'regression_range_size': regression_range_size
            }
        },
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '1',
    }

    self.assertEqual(expected_compile_result, compile_result)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_compile_result, try_job.compile_results[-1])
    self.assertEqual(analysis_status.RUNNING, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertEqual(try_job_data.regression_range_size, regression_range_size)
    self.assertIsInstance(try_job_data.start_time, datetime)

  @mock.patch.object(swarming_util, 'GetStepLog')
  @mock.patch.object(monitor_try_job_pipeline, 'buildbucket_client')
  def testGetTryJobsForTestMissingTryJobData(self, mock_buildbucket,
                                             mock_report):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '3'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.test_results = [{
        'report': None,
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': try_job_id,
    }]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    data = [{
        'build': {
            'id': '3',
            'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
            'status': 'STARTED'
        }
    }, {
        'error': {
            'reason': 'BUILD_NOT_FOUND',
            'message': 'message',
        }
    }, {
        'build': {
            'id': '3',
            'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
            'status': 'STARTED'
        }
    }, {
        'error': {
            'reason': 'BUILD_NOT_FOUND',
            'message': 'message',
        }
    }, {
        'build': {
            'id': '3',
            'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
            'status': 'COMPLETED',
        }
    }]

    report = {
        'result': {
            'rev1': {
                'a_test': {
                    'status': 'passed',
                    'valid': True
                }
            },
            'rev2': {
                'a_test': {
                    'status': 'failed',
                    'valid': True,
                    'failures': ['test1', 'test2']
                }
            }
        }
    }

    get_tryjobs_responses = [
        [(None, buildbucket_client.BuildbucketBuild(data[0]['build']))],
        [(buildbucket_client.BuildbucketError(data[1]['error']), None)],
        [(None, buildbucket_client.BuildbucketBuild(data[2]['build']))],
        [(buildbucket_client.BuildbucketError(data[3]['error']), None)],
        [(None, buildbucket_client.BuildbucketBuild(data[4]['build']))],
    ]
    mock_buildbucket.GetTryJobs.side_effect = get_tryjobs_responses
    mock_report.return_value = report

    monitor_pipeline = MonitorTryJobPipeline()
    monitor_pipeline.start_test()
    monitor_pipeline.run(try_job.key.urlsafe(), failure_type.TEST, try_job_id)
    monitor_pipeline.run(try_job.key.urlsafe(), failure_type.TEST, try_job_id)
    # Since run() calls callback() immediately, we use -1.
    for _ in range(len(get_tryjobs_responses) - 1):
      monitor_pipeline.callback(callback_params=monitor_pipeline.last_params)

    # Reload from ID to get all internal properties in sync.
    monitor_pipeline = MonitorTryJobPipeline.from_id(
        monitor_pipeline.pipeline_id)
    monitor_pipeline.finalized()
    test_result = monitor_pipeline.outputs.default.value

    expected_test_result = {
        'report': {
            'result': {
                'rev1': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['test1', 'test2']
                    }
                }
            }
        },
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '3',
    }
    self.assertEqual(expected_test_result, test_result)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_test_result, try_job.test_results[-1])
    self.assertEqual(analysis_status.RUNNING, try_job.status)

  @mock.patch.object(swarming_util, 'GetStepLog')
  @mock.patch.object(monitor_try_job_pipeline, 'buildbucket_client')
  def testGetTryJobsForFlakeSuccess(self, mock_buildbucket, mock_report):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    git_hash = 'a1b2c3d4'
    try_job_id = '1'

    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, git_hash)
    try_job.flake_results = [{
        'report': None,
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '1',
    }]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = (
        'https://build.chromium.org/p/m/builders/b/builds/1234')
    try_job_data.put()

    build_response = {
        'id': '1',
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'status': 'COMPLETED',
    }
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
                    }
                }
            }
        }
    }
    mock_buildbucket.GetTryJobs.return_value = [
        (None, buildbucket_client.BuildbucketBuild(build_response))
    ]
    mock_report.return_value = report

    monitor_pipeline = MonitorTryJobPipeline()
    monitor_pipeline.start_test()
    monitor_pipeline.run(try_job.key.urlsafe(), failure_type.FLAKY_TEST,
                         try_job_id)
    monitor_pipeline.callback(callback_params=monitor_pipeline.last_params)

    # Reload from ID to get all internal properties in sync.
    monitor_pipeline = MonitorTryJobPipeline.from_id(
        monitor_pipeline.pipeline_id)
    monitor_pipeline.finalized()
    flake_result = monitor_pipeline.outputs.default.value

    expected_flake_result = {
        'report': {
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
                        }
                    }
                }
            }
        },
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '1',
    }

    self.assertEqual(expected_flake_result, flake_result)

    try_job = FlakeTryJob.Get(master_name, builder_name, step_name, test_name,
                              git_hash)
    self.assertEqual(expected_flake_result, try_job.flake_results[-1])
    self.assertEqual(analysis_status.RUNNING, try_job.status)

    try_job_data = FlakeTryJobData.Get(try_job_id)
    self.assertEqual(try_job_data.last_buildbucket_response, build_response)

  def testReturnNoneIfNoTryJobId(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    monitor_pipeline = MonitorTryJobPipeline()
    monitor_pipeline.start_test()
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    monitor_pipeline.run(try_job.key.urlsafe(), failure_type.TEST, None)

    # Reload from ID to get all internal properties in sync.
    monitor_pipeline = MonitorTryJobPipeline.from_id(
        monitor_pipeline.pipeline_id)
    monitor_pipeline.finalized()
    test_result = monitor_pipeline.outputs.default.value
    self.assertIsNone(test_result)

  @mock.patch.object(swarming_util, 'GetStepLog')
  @mock.patch.object(monitor_try_job_pipeline, 'buildbucket_client')
  def testGetTryJobsForCompileSuccessBackwardCompatibleCallback(
      self, mock_buildbucket, mock_report):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    regression_range_size = 2

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = (
        'https://build.chromium.org/p/m/builders/b/builds/1234')
    try_job_data.put()
    try_job.compile_results = [{
        'report': None,
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '1',
    }]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    report = {
        'result': {
            'rev1': 'passed',
            'rev2': 'failed'
        },
        'metadata': {
            'regression_range_size': 2
        }
    }

    build_response = {
        'id': '1',
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367574000000',
    }
    mock_buildbucket.GetTryJobs.return_value = [
        (None, buildbucket_client.BuildbucketBuild(build_response))
    ]
    mock_report.return_value = report

    monitor_pipeline = MonitorTryJobPipeline(try_job.key.urlsafe(),
                                             failure_type.COMPILE, try_job_id)
    monitor_pipeline.start_test()
    monitor_pipeline.run(try_job.key.urlsafe(), failure_type.COMPILE,
                         try_job_id)
    monitor_pipeline.callback(**monitor_pipeline.last_params)

    # Reload from ID to get all internal properties in sync.
    monitor_pipeline = MonitorTryJobPipeline.from_id(
        monitor_pipeline.pipeline_id)
    monitor_pipeline.finalized()
    compile_result = monitor_pipeline.outputs.default.value

    expected_compile_result = {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            },
            'metadata': {
                'regression_range_size': regression_range_size
            }
        },
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '1',
    }

    self.assertEqual(expected_compile_result, compile_result)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_compile_result, try_job.compile_results[-1])
    self.assertEqual(analysis_status.RUNNING, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertEqual(try_job_data.regression_range_size, regression_range_size)
    self.assertIsInstance(try_job_data.start_time, datetime)

  @mock.patch.object(logging, 'warning')
  @mock.patch.object(
      MonitorTryJobPipeline,
      'get_callback_task',
      side_effect=taskqueue.TombstonedTaskError)
  def testDelayCallbackException(self, _, mocked_logging):
    monitor_pipeline = MonitorTryJobPipeline()
    monitor_pipeline.start_test()
    monitor_pipeline.delay_callback(
        60, monitor_pipeline.last_params, name='name')
    mocked_logging.assert_called()

  @mock.patch.object(
      try_job_service,
      'OnGetTryJobError',
      side_effect=exceptions.RetryException('error_reason', 'error_message'))
  @mock.patch.object(monitor_try_job_pipeline, 'buildbucket_client')
  def testMonitorTryJobMaxError(self, mock_buildbucket, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.put()
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = (
        'https://build.chromium.org/p/m/builders/b/builds/1234')
    try_job_data.put()

    error_data = {'reason': 'BUILD_NOT_FOUND', 'message': 'message'}
    error = buildbucket_client.BuildbucketError(error_data)
    mock_buildbucket.GetTryJobs.return_value = [(error, None)]

    monitor_pipeline = MonitorTryJobPipeline()
    monitor_pipeline.start_test()
    with self.assertRaises(pipeline.Retry):
      monitor_pipeline.run(try_job.key.urlsafe(), failure_type.COMPILE,
                           try_job_id)
