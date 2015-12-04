# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from common import buildbucket_client
from model.wf_try_job import WfTryJob
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline

class MonitorTryJobPipelineTest(testing.AppengineTestCase):
  def _Mock_GetTryJobs(self, build_ids):
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
      results = []
      for build_id in build_ids:
        build_error = data.get(build_id)
        if build_error.get('error'):  # pragma: no cover
          results.append((
              buildbucket_client.BuildbucketError(build_error['error']), None))
        else:
          results.append((
              None, buildbucket_client.BuildbucketBuild(build_error['build'])))
      return results
    self.mock(buildbucket_client, 'GetTryJobs', Mocked_GetTryJobs)

  def testGetTryJobsSuccess(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_ids = ['1']

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.put()
    self._Mock_GetTryJobs(try_job_ids)

    pipeline = MonitorTryJobPipeline()
    results = pipeline.run(
      master_name, builder_name, build_number, try_job_ids)

    expected_results = [
        {
            'result': [
                ['rev1', 'passed'],
                ['rev2', 'failed']
            ],
            'url': 'url'
        }
    ]
    self.assertEqual(expected_results, results)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(expected_results, try_job.results)
