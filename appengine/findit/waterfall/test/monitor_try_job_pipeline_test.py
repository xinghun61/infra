# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
from testing_utils import testing

from common import buildbucket_client
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline
from waterfall.try_job_type import TryJobType


class MonitorTryJobPipelineTest(testing.AppengineTestCase):

  def _Mock_GetTryJobs(self, build_id):
    def Mocked_GetTryJobs(*_):
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
              'error': {
                  'reason': 'BUILD_NOT_FOUND',
                  'message': 'message',
              }
          },
          '3': {
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
    self.mock(buildbucket_client, 'GetTryJobs', Mocked_GetTryJobs)

  def testMicrosecondsToDatetime(self):
    self.assertEqual(
        datetime(2016, 2, 1, 14, 59, 34, 0),
        MonitorTryJobPipeline._MicrosecondsToDatetime(1454367574000000))
    self.assertIsNone(MonitorTryJobPipeline._MicrosecondsToDatetime(None))

  def testUpdateTryJobMetadataForBuildError(self):
    error_data = {
        'reason': 'BUILD_NOT_FOUND',
        'message': 'message'
    }
    error = buildbucket_client.BuildbucketError(error_data)
    try_job_data = WfTryJobData.Create('1')

    MonitorTryJobPipeline._UpdateTryJobMetadataForBuildError(
        try_job_data, error)
    self.assertEqual(try_job_data.error, error_data)

  def testUpdateTryJobMetadataForCompletedBuild(self):
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
    try_job_data = WfTryJobData.Create(try_job_id)

    MonitorTryJobPipeline._UpdateTryJobMetadataForCompletedBuild(
        try_job_data, build, None, timed_out=False)
    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.error)
    self.assertEqual(try_job_data.regression_range_size, 2)
    self.assertEqual(try_job_data.number_of_commits_analyzed, 2)
    self.assertEqual(try_job_data.end_time, datetime(2016, 2, 1, 14, 59, 34, 0))
    self.assertEqual(try_job_data.request_time,
                     datetime(2016, 2, 1, 14, 59, 30))
    self.assertEqual(try_job_data.try_job_url, url)

    MonitorTryJobPipeline._UpdateTryJobMetadataForCompletedBuild(
        try_job_data, build, None, timed_out=True)
    self.assertEqual(try_job_data.error,
                     {'message': MonitorTryJobPipeline.TIMEOUT,
                      'reason': MonitorTryJobPipeline.TIMEOUT})

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
    try_job.status = wf_analysis_status.ANALYZING
    try_job.put()
    self._Mock_GetTryJobs(try_job_id)

    pipeline = MonitorTryJobPipeline()
    compile_result = pipeline.run(
        master_name, builder_name, build_number, TryJobType.COMPILE,
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
    self.assertEqual(wf_analysis_status.ANALYZING, try_job.status)

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
            'try_job_id': '3',
        }
    ]
    try_job.status = wf_analysis_status.ANALYZING
    try_job.put()
    self._Mock_GetTryJobs(try_job_id)

    pipeline = MonitorTryJobPipeline()
    test_result = pipeline.run(
        master_name, builder_name, build_number, TryJobType.TEST,
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
    self.assertEqual(wf_analysis_status.ANALYZING, try_job.status)
