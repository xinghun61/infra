# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import mock
import time

from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from common.waterfall import try_job_error
from model import analysis_status
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall import monitor_try_job_pipeline
from waterfall import waterfall_config
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline
from waterfall.test import wf_testcase


class MonitorTryJobPipelineTest(wf_testcase.WaterfallTestCase):

  def testDictsAreEqual(self):
    self.assertTrue(monitor_try_job_pipeline._DictsAreEqual(None, None))
    self.assertTrue(monitor_try_job_pipeline._DictsAreEqual({}, {}))
    self.assertTrue(monitor_try_job_pipeline._DictsAreEqual({'a': 1}, {'a': 1}))
    self.assertTrue(monitor_try_job_pipeline._DictsAreEqual(
        {'a': 1},
        {'a': 1, 'b': 2},
        exclude_keys=['b']))
    self.assertTrue(monitor_try_job_pipeline._DictsAreEqual(
        {'a': 1, 'b': 1},
        {'a': 1, 'b': 2},
        exclude_keys=['b']))
    self.assertTrue(monitor_try_job_pipeline._DictsAreEqual(
        {'a': 1},
        {},
        exclude_keys=['a']))
    self.assertFalse(monitor_try_job_pipeline._DictsAreEqual(
        {'a': 1},
        {'a': 2}))
    self.assertFalse(monitor_try_job_pipeline._DictsAreEqual(
        {'a': 1, 'b': 2},
        {'a': 1}))
    self.assertFalse(monitor_try_job_pipeline._DictsAreEqual(
        {'a': 1},
        {'a': 1, 'b': 2}))

  def testUpdateTryJobMetadataForBuildError(self):
    error_data = {
        'reason': 'BUILD_NOT_FOUND',
        'message': 'message'
    }
    error = buildbucket_client.BuildbucketError(error_data)
    try_job_data = WfTryJobData.Create('1')
    try_job_data.try_job_key = WfTryJob.Create('m', 'b', 123).key

    monitor_try_job_pipeline._UpdateTryJobMetadata(
        try_job_data, failure_type.COMPILE, None, error, False)
    self.assertEqual(try_job_data.error, error_data)

  def testUpdateTryJobMetadata(self):
    try_job_id = '1'
    url = 'url'
    build_data = {
        'id': try_job_id,
        'url': url,
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
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
    build = buildbucket_client.BuildbucketBuild(build_data)
    expected_error_dict = {
        'message': 'Try job monitoring was abandoned.',
        'reason': ('Timeout after %s hours' %
                   waterfall_config.GetTryJobSettings().get(
                       'job_timeout_hours'))
    }
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = WfTryJob.Create('m', 'b', 123).key

    monitor_try_job_pipeline._UpdateTryJobMetadata(
        try_job_data, failure_type.COMPILE, build, None, False)
    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.error)
    self.assertEqual(try_job_data.regression_range_size, 2)
    self.assertEqual(try_job_data.number_of_commits_analyzed, 2)
    self.assertEqual(try_job_data.end_time, datetime(2016, 2, 1, 22, 59, 34))
    self.assertEqual(try_job_data.request_time,
                     datetime(2016, 2, 1, 22, 59, 30))
    self.assertEqual(try_job_data.try_job_url, url)

    monitor_try_job_pipeline._UpdateTryJobMetadata(
        try_job_data, failure_type.COMPILE, build, None, True)
    self.assertEqual(try_job_data.error, expected_error_dict)
    self.assertEqual(try_job_data.error_code, try_job_error.TIMEOUT)

  @mock.patch.object(monitor_try_job_pipeline, 'buildbucket_client')
  def testGetTryJobsForCompileSuccess(self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    regression_range_size = 2

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()
    try_job.compile_results = [
        {
            'report': None,
            'url': 'url',
            'try_job_id': '1',
        }
    ]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    build_response = {
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
    mock_module.GetTryJobs.return_value = [
        (None, buildbucket_client.BuildbucketBuild(build_response))]

    pipeline = MonitorTryJobPipeline()
    pipeline.start_test()
    pipeline.run(try_job.key.urlsafe(), failure_type.COMPILE, try_job_id)
    pipeline.callback(pipeline.last_params)

    # Reload from ID to get all internal properties in sync.
    pipeline = MonitorTryJobPipeline.from_id(pipeline.pipeline_id)
    compile_result = pipeline.outputs.default.value

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
        'url': 'url',
        'try_job_id': '1',
    }

    self.assertEqual(expected_compile_result, compile_result)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_compile_result, try_job.compile_results[-1])
    self.assertEqual(analysis_status.RUNNING, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertEqual(try_job_data.regression_range_size, regression_range_size)

  @mock.patch.object(monitor_try_job_pipeline, 'buildbucket_client')
  def testGetTryJobsForCompileSuccessSerializedCallback(self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    regression_range_size = 2

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()
    try_job.compile_results = [
        {
            'report': None,
            'url': 'url',
            'try_job_id': '1',
        }
    ]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    build_response = {
        'id': '1',
        'url': 'url',
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367574000000',
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
    mock_module.GetTryJobs.return_value = [
        (None, buildbucket_client.BuildbucketBuild(build_response))]

    pipeline = MonitorTryJobPipeline()
    pipeline.start_test()
    pipeline.run(try_job.key.urlsafe(), failure_type.COMPILE, try_job_id)
    pipeline.callback(json.dumps(pipeline.last_params))

    # Reload from ID to get all internal properties in sync.
    pipeline = MonitorTryJobPipeline.from_id(pipeline.pipeline_id)
    compile_result = pipeline.outputs.default.value

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
        'url': 'url',
        'try_job_id': '1',
    }

    self.assertEqual(expected_compile_result, compile_result)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_compile_result, try_job.compile_results[-1])
    self.assertEqual(analysis_status.RUNNING, try_job.status)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertEqual(try_job_data.regression_range_size, regression_range_size)
    self.assertIsInstance(try_job_data.start_time, datetime)

  @mock.patch.object(monitor_try_job_pipeline, 'buildbucket_client')
  def testGetTryJobsForTestMissingTryJobData(self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '3'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.test_results = [
        {
            'report': None,
            'url': 'url',
            'try_job_id': try_job_id,
        }
    ]
    try_job.status = analysis_status.RUNNING
    try_job.put()


    data = [
        {
            'build': {
                'id': '3',
                'url': 'url',
                'status': 'STARTED'
            }
        },
        {
            'error': {
                'reason': 'BUILD_NOT_FOUND',
                'message': 'message',
            }
        },
        {
            'build': {
                'id': '3',
                'url': 'url',
                'status': 'STARTED'
            }
        },
        {
            'error': {
                'reason': 'BUILD_NOT_FOUND',
                'message': 'message',
            }
        },
        {
            'build': {
                'id': '3',
                'url': 'url',
                'status': 'COMPLETED',
                'result_details_json': json.dumps({
                    'properties': {
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
                        }
                    }
                })
            }
        }
    ]

    get_tryjobs_responses = [
        [(None, buildbucket_client.BuildbucketBuild(data[0]['build']))],
        [(buildbucket_client.BuildbucketError(data[1]['error']), None)],
        [(None, buildbucket_client.BuildbucketBuild(data[2]['build']))],
        [(buildbucket_client.BuildbucketError(data[3]['error']), None)],
        [(None, buildbucket_client.BuildbucketBuild(data[4]['build']))],
    ]
    mock_module.GetTryJobs.side_effect = get_tryjobs_responses

    pipeline = MonitorTryJobPipeline()
    pipeline.start_test()
    pipeline.run(try_job.key.urlsafe(), failure_type.TEST, try_job_id)
    pipeline.run(try_job.key.urlsafe(), failure_type.TEST, try_job_id)
    # Since run() calls callback() immediately, we use -1.
    for _ in range (len(get_tryjobs_responses) - 1):
      pipeline.callback(pipeline.last_params)

    # Reload from ID to get all internal properties in sync.
    pipeline = MonitorTryJobPipeline.from_id(pipeline.pipeline_id)
    test_result = pipeline.outputs.default.value

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
        'url': 'url',
        'try_job_id': '3',
    }
    self.assertEqual(expected_test_result, test_result)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_test_result, try_job.test_results[-1])
    self.assertEqual(analysis_status.RUNNING, try_job.status)

  @mock.patch.object(monitor_try_job_pipeline, 'buildbucket_client')
  def testGetTryJobsForTestSuccess(self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '3'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.test_results = [
        {
            'report': None,
            'url': 'url',
            'try_job_id': try_job_id,
        }
    ]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    data = [
        {
            'build': {
                'id': '3',
                'url': 'url',
                'status': 'STARTED'
            }
        },
        {
            'error': {
                'reason': 'BUILD_NOT_FOUND',
                'message': 'message',
            }
        },
        {
            'build': {
                'id': '3',
                'url': 'url',
                'status': 'STARTED'
            }
        },
        {
            'error': {
                'reason': 'BUILD_NOT_FOUND',
                'message': 'message',
            }
        },
        {
            'build': {
                'id': '3',
                'url': 'url',
                'status': 'COMPLETED',
                'result_details_json': json.dumps({
                    'properties': {
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
                        }
                    }
                })
            }
        }
    ]

    get_tryjobs_responses = [
        [(None, buildbucket_client.BuildbucketBuild(data[0]['build']))],
        [(buildbucket_client.BuildbucketError(data[1]['error']), None)],
        [(None, buildbucket_client.BuildbucketBuild(data[2]['build']))],
        [(buildbucket_client.BuildbucketError(data[3]['error']), None)],
        [(None, buildbucket_client.BuildbucketBuild(data[4]['build']))],
    ]
    mock_module.GetTryJobs.side_effect = get_tryjobs_responses

    pipeline = MonitorTryJobPipeline()
    pipeline.start_test()
    pipeline.run(try_job.key.urlsafe(), failure_type.TEST, try_job_id)
    pipeline.run(try_job.key.urlsafe(), failure_type.TEST, try_job_id)
    # Since run() calls callback() immediately, we use -1.
    for _ in range (len(get_tryjobs_responses) - 1):
      pipeline.callback(pipeline.last_params)

    # Reload from ID to get all internal properties in sync.
    pipeline = MonitorTryJobPipeline.from_id(pipeline.pipeline_id)
    test_result = pipeline.outputs.default.value

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
        'url': 'url',
        'try_job_id': '3',
    }
    self.assertEqual(expected_test_result, test_result)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_test_result, try_job.test_results[-1])
    self.assertEqual(analysis_status.RUNNING, try_job.status)

  @mock.patch.object(monitor_try_job_pipeline, 'buildbucket_client')
  def testGetTryJobsForFlakeSuccess(self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    git_hash = 'a1b2c3d4'
    try_job_id = '1'

    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, git_hash)
    try_job.flake_results = [
        {
            'report': None,
            'url': 'url',
            'try_job_id': '1',
        }
    ]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    build_response = {
        'id': '1',
        'url': 'url',
        'status': 'COMPLETED',
        'result_details_json': json.dumps({
            'properties': {
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
                }
            }
        })
    }

    mock_module.GetTryJobs.return_value = [
        (None, buildbucket_client.BuildbucketBuild(build_response))]

    pipeline = MonitorTryJobPipeline()
    pipeline.start_test()
    pipeline.run(try_job.key.urlsafe(), failure_type.FLAKY_TEST, try_job_id)
    pipeline.callback(pipeline.last_params)

    # Reload from ID to get all internal properties in sync.
    pipeline = MonitorTryJobPipeline.from_id(pipeline.pipeline_id)
    flake_result = pipeline.outputs.default.value

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
        'url': 'url',
        'try_job_id': '1',
    }

    self.assertEqual(expected_flake_result, flake_result)

    try_job = FlakeTryJob.Get(
        master_name, builder_name, step_name, test_name, git_hash)
    self.assertEqual(expected_flake_result, try_job.flake_results[-1])
    self.assertEqual(analysis_status.RUNNING, try_job.status)

    try_job_data = FlakeTryJobData.Get(try_job_id)
    self.assertEqual(try_job_data.last_buildbucket_response, build_response)

  def testUpdateTryJobResultAnalyzing(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '3'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.put()

    pipeline = MonitorTryJobPipeline()
    pipeline._UpdateTryJobResult(
        try_job.key.urlsafe(), failure_type.TEST, try_job_id, 'url',
        buildbucket_client.BuildbucketBuild.STARTED)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.RUNNING, try_job.status)

  def testUpdateFlakeTryJobResult(self):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    git_hash = 'a1b2c3d4'
    try_job_id = '2'
    try_job = FlakeTryJob.Create(
        master_name, builder_name, step_name, test_name, git_hash)
    try_job.put()

    pipeline = MonitorTryJobPipeline()
    pipeline._UpdateTryJobResult(
        try_job.key.urlsafe(), failure_type.FLAKY_TEST, try_job_id, 'url',
        buildbucket_client.BuildbucketBuild.STARTED)
    try_job = FlakeTryJob.Get(
        master_name, builder_name, step_name, test_name, git_hash)
    self.assertEqual(analysis_status.RUNNING, try_job.status)

  def testGetErrorForNoError(self):
    build_response = {
        'id': 1,
        'url': 'url',
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
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
    self.assertEqual(
        monitor_try_job_pipeline._GetError(build_response, None, False),
        (None, None))
    self.assertEqual(monitor_try_job_pipeline._GetError({}, None, False),
                     (None, None))

  def testGetErrorForTimeout(self):
    expected_error_dict = {
        'message': 'Try job monitoring was abandoned.',
        'reason': ('Timeout after %s hours' %
                   waterfall_config.GetTryJobSettings().get(
                       'job_timeout_hours'))
    }

    self.assertEqual(
        monitor_try_job_pipeline._GetError({}, None, True),
        (expected_error_dict, try_job_error.TIMEOUT))

  def testGetErrorForBuildbucketReportedError(self):
    build_response = {
        'result_details_json': json.dumps({
            'error': {
                'message': 'Builder b not found'
            }
        })
    }

    expected_error_dict = {
        'message': 'Buildbucket reported an error.',
        'reason': 'Builder b not found'
    }

    self.assertEqual(
        monitor_try_job_pipeline._GetError(build_response, None, False),
        (expected_error_dict, try_job_error.CI_REPORTED_ERROR))

  def testGetErrorUnknown(self):
    build_response = {
        'result_details_json': json.dumps({
            'error': {
                'abc': 'abc'
            }
        })
    }

    expected_error_dict = {
        'message': 'Buildbucket reported an error.',
        'reason': MonitorTryJobPipeline.UNKNOWN
    }

    self.assertEqual(
        monitor_try_job_pipeline._GetError(build_response, None, False),
        (expected_error_dict, try_job_error.CI_REPORTED_ERROR))

  def testGetErrorInfraFailure(self):
    build_response = {
        'result': 'FAILED',
        'failure_reason': 'INFRA_FAILURE',
        'result_details_json': json.dumps({
            'properties': {
                'report': {
                    'metadata': {
                        'infra_failure': True
                    }
                }
            }
        })
    }

    expected_error_dict = {
        'message': 'Try job encountered an infra issue during execution.',
        'reason': MonitorTryJobPipeline.UNKNOWN
    }

    self.assertEqual(
        monitor_try_job_pipeline._GetError(build_response, None, False),
        (expected_error_dict, try_job_error.INFRA_FAILURE))

  def testGetErrorUnexpectedBuildFailure(self):
    build_response = {
        'result': 'FAILED',
        'failure_reason': 'BUILD_FAILURE',
        'result_details_json': json.dumps({
            'properties': {
                'report': {
                    'metadata': {
                        'infra_failure': True
                    }
                }
            }
        })
    }

    expected_error_dict = {
        'message': 'Buildbucket reported a general error.',
        'reason': MonitorTryJobPipeline.UNKNOWN
    }

    self.assertEqual(
        monitor_try_job_pipeline._GetError(build_response, None, False),
        (expected_error_dict, try_job_error.INFRA_FAILURE))

  def testGetErrorUnknownBuildbucketFailure(self):
    build_response = {
        'result': 'FAILED',
        'failure_reason': 'SOME_FAILURE',
        'result_details_json': json.dumps({
            'properties': {
                'report': {}
            }
        })
    }

    expected_error_dict = {
        'message': 'SOME_FAILURE',
        'reason': MonitorTryJobPipeline.UNKNOWN
    }

    self.assertEqual(
        monitor_try_job_pipeline._GetError(build_response, None, False),
        (expected_error_dict, try_job_error.UNKNOWN))

  def testGetErrorReportMissing(self):
    build_response = {
        'result_details_json': json.dumps({
            'properties': {}
        })
    }

    expected_error_dict = {
        'message': 'No result report was found.',
        'reason': MonitorTryJobPipeline.UNKNOWN
    }

    self.assertEqual(
        monitor_try_job_pipeline._GetError(build_response, None, False),
        (expected_error_dict, try_job_error.UNKNOWN))

  def testReturnNoneIfNoTryJobId(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    pipeline = MonitorTryJobPipeline()
    pipeline.start_test()
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    pipeline.run(try_job.key.urlsafe(), failure_type.TEST, None)

    # Reload from ID to get all internal properties in sync.
    pipeline = MonitorTryJobPipeline.from_id(pipeline.pipeline_id)
    test_result = pipeline.outputs.default.value
    self.assertIsNone(test_result)
