# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import time

from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from common.waterfall import try_job_error
from model import analysis_status
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall import monitor_try_job_pipeline
from waterfall import waterfall_config
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline
from waterfall.test import wf_testcase


# A counter to enable different responses to requests in a loop.
REQUEST_COUNTER = {
    '1': 0,
    '2': 0,
    '3': 0
}


class MonitorTryJobPipelineTest(wf_testcase.WaterfallTestCase):

  def _MockGetTryJobs(self, build_id):
    def Mocked_GetTryJobs(*_):
      data = {
          '1': [
              {
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
              }
          ],
          '3': [
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
      }
      try_job_results = []
      build_error = data.get(build_id)[REQUEST_COUNTER[build_id]]
      if build_error.get('error'):
        try_job_results.append((
            buildbucket_client.BuildbucketError(build_error['error']), None))
      else:
        try_job_results.append((
            None, buildbucket_client.BuildbucketBuild(build_error['build'])))
      REQUEST_COUNTER[build_id] += 1
      return try_job_results

    self.mock(buildbucket_client, 'GetTryJobs', Mocked_GetTryJobs)

  def setUp(self):
    super(MonitorTryJobPipelineTest, self).setUp()
    self.mock(time, 'sleep', lambda x: None)

  def testMicrosecondsToDatetime(self):
    self.assertEqual(
        datetime(2016, 2, 1, 22, 59, 34),
        monitor_try_job_pipeline._MicrosecondsToDatetime(1454367574000000))
    self.assertIsNone(monitor_try_job_pipeline._MicrosecondsToDatetime(None))

  def testUpdateTryJobMetadataForBuildError(self):
    error_data = {
        'reason': 'BUILD_NOT_FOUND',
        'message': 'message'
    }
    error = buildbucket_client.BuildbucketError(error_data)
    try_job_data = WfTryJobData.Create('1')

    monitor_try_job_pipeline._UpdateTryJobMetadata(
        try_job_data, None, None, error, False)
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

    monitor_try_job_pipeline._UpdateTryJobMetadata(
        try_job_data, None, build, None, False)
    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.error)
    self.assertEqual(try_job_data.regression_range_size, 2)
    self.assertEqual(try_job_data.number_of_commits_analyzed, 2)
    self.assertEqual(try_job_data.end_time, datetime(2016, 2, 1, 22, 59, 34))
    self.assertEqual(try_job_data.request_time,
                     datetime(2016, 2, 1, 22, 59, 30))
    self.assertEqual(try_job_data.try_job_url, url)

    monitor_try_job_pipeline._UpdateTryJobMetadata(
        try_job_data, None, build, None, True)
    self.assertEqual(try_job_data.error, expected_error_dict)
    self.assertEqual(try_job_data.error_code, try_job_error.TIMEOUT)

  def testGetTryJobsForCompileSuccess(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    regression_range_size = 2

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Create(try_job_id)
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
    self._MockGetTryJobs(try_job_id)

    pipeline = MonitorTryJobPipeline()
    compile_result = pipeline.run(
        master_name, builder_name, build_number, failure_type.COMPILE,
        try_job_id)

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

  def testGetTryJobsForTestSuccess(self):
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
    try_job_data.put()

    self._MockGetTryJobs(try_job_id)

    pipeline = MonitorTryJobPipeline()
    test_result = pipeline.run(
        master_name, builder_name, build_number, failure_type.TEST,
        try_job_id)

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

  def testUpdateTryJobResultAnalyzing(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '3'

    try_job = WfTryJob.Create(master_name, builder_name, build_number).put()

    pipeline = MonitorTryJobPipeline()
    pipeline._UpdateTryJobResult(
        buildbucket_client.BuildbucketBuild.STARTED, master_name, builder_name,
        build_number, failure_type.TEST, try_job_id, 'url')
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
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
