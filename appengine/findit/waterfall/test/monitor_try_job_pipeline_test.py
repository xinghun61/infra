# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from common import buildbucket_client
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline

class MonitorTryJobPipelineTest(testing.AppengineTestCase):
  def _Mock_GetTryJobs(self, build_id):
    def Mocked_GetTryJobs(*_):
      data = {
          '1': {
              'build': {
                  'id': '1',
                  'url': 'url',
                  'status': 'COMPLETED',
                  'result_details_json': (
                      '{"properties": {"result": [["rev1", "passed"],'
                      ' ["rev2", "failed"]]}}')
              }
          },
          '2': {
              'error': {
                  'reason': 'BUILD_NOT_FOUND',
                  'message': 'message',
              }
          }
      }
      compile_results = []
      build_error = data.get(build_id)
      if build_error.get('error'):  # pragma: no cover
        compile_results.append((
            buildbucket_client.BuildbucketError(build_error['error']), None))
      else:
        compile_results.append((
            None, buildbucket_client.BuildbucketBuild(build_error['build'])))
      return compile_results
    self.mock(buildbucket_client, 'GetTryJobs', Mocked_GetTryJobs)

  def testGetTryJobsForCompileSuccess(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [
        {
            'result': None,
            'url': 'url',
            'try_job_id': '1',
        }
    ]
    try_job.status = wf_analysis_status.ANALYZING
    try_job.put()
    self._Mock_GetTryJobs(try_job_id)

    pipeline = MonitorTryJobPipeline()
    compile_result = pipeline.run(
        master_name, builder_name, build_number, try_job_id)

    expected_compile_result = {
        'result': [
            ['rev1', 'passed'],
            ['rev2', 'failed']
        ],
        'url': 'url',
        'try_job_id': '1',
    }
    self.assertEqual(expected_compile_result, compile_result)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_compile_result, try_job.compile_results[-1])
    self.assertEqual(wf_analysis_status.ANALYZING, try_job.status)
