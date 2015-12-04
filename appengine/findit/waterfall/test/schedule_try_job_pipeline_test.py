# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from common import buildbucket_client
from pipeline_wrapper import pipeline
from waterfall.schedule_try_job_pipeline import ScheduleTryJobPipeline
from waterfall import waterfall_config


class ScheduleTryjobPipelineTest(testing.AppengineTestCase):
  def _Mock_GetTrybotForWaterfallBuilder(self, *_):
    def Mocked_GetTrybotForWaterfallBuilder(*_):
      return 'linux_chromium_variable', 'master.tryserver.chromium.linux'
    self.mock(waterfall_config, 'GetTrybotForWaterfallBuilder',
              Mocked_GetTrybotForWaterfallBuilder)

  def _Mock_TriggerTryJobs(self, responses):
    def Mocked_TriggerTryJobs(*_):
      results = []
      for response in responses:
        if response.get('error'):  # pragma: no cover
          results.append((
              buildbucket_client.BuildbucketError(response['error']), None))
        else:
          results.append((
              None, buildbucket_client.BuildbucketBuild(response['build'])))
      return results
    self.mock(buildbucket_client, 'TriggerTryJobs', Mocked_TriggerTryJobs)

  def testSuccessfullyScheduleNewTryJob(self):
    master_name = 'm'
    builder_name = 'b'
    revisions = '[]'

    responses = [
        {
          'build': {
              'id': '1',
              'url': 'url',
              'status': 'SCHEDULED',
          }
        }
    ]
    self._Mock_GetTrybotForWaterfallBuilder(master_name, builder_name)
    self._Mock_TriggerTryJobs(responses)

    try_job_pipeline = ScheduleTryJobPipeline()
    try_job_id = try_job_pipeline.run(
        master_name, builder_name, revisions)

    self.assertEqual('1', try_job_id)
