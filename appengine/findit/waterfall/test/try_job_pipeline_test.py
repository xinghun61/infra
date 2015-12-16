# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from common import buildbucket_client
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from pipeline_wrapper import pipeline_handlers
from waterfall.try_job_pipeline import TryJobPipeline
from waterfall import waterfall_config


class TryJobPipelineTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  def _Mock_GetTrybotForWaterfallBuilder(self, *_):
    def Mocked_GetTrybotForWaterfallBuilder(*_):
      return 'linux_chromium_variable', 'master.tryserver.chromium.linux'
    self.mock(waterfall_config, 'GetTrybotForWaterfallBuilder',
              Mocked_GetTrybotForWaterfallBuilder)

  def _Mock_TriggerTryJobs(self, responses):
    def Mocked_TriggerTryJobs(*_):
      compile_results = []
      for response in responses:
        if response.get('error'):  # pragma: no cover
          compile_results.append((
              buildbucket_client.BuildbucketError(response['error']), None))
        else:
          compile_results.append((
              None, buildbucket_client.BuildbucketBuild(response['build'])))
      return compile_results
    self.mock(buildbucket_client, 'TriggerTryJobs', Mocked_TriggerTryJobs)

  def _Mock_GetTryJobs(self, build_id):
    def Mocked_GetTryJobs(*_):
      data = {
          '1': {
              'build': {
                  'id': '1',
                  'url': 'url',
                  'status': 'COMPLETED',
                  'result_details_json':(
                      '{"properties": {"result": [["rev1", "passed"],'
                      ' ["rev2", "failed"]]}}')
              }
          },
          '3': {
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

  def testSuccessfullyScheduleNewTryJobForCompile(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    good_revision = 'rev1'
    bad_revision = 'rev2'

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
    self._Mock_GetTryJobs('1')

    WfTryJob.Create(master_name, builder_name, build_number).put()

    root_pipeline = TryJobPipeline(
        master_name, builder_name, build_number, good_revision, bad_revision)
    root_pipeline.start()
    self.execute_queued_tasks()

    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    expected_compile_results = [
        {
            'result': [
                ['rev1', 'passed'],
                ['rev2', 'failed']
            ],
            'url': 'url',
            'try_job_id': '1',
        }
    ]
    self.assertEqual(expected_compile_results, try_job.compile_results)

  def testPipelineAbortedWithTryJobResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    WfTryJob.Create(master_name, builder_name, build_number).put()

    root_pipeline = TryJobPipeline(
        master_name, builder_name, build_number, 'rev1', 'rev2')
    root_pipeline._LogUnexpectedAbort(True)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(wf_analysis_status.ERROR, try_job.status)

  def testPipelineAbortedWithOutTryJobResult(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    root_pipeline = TryJobPipeline(
        master_name, builder_name, build_number, 'rev1', 'rev2')
    root_pipeline._LogUnexpectedAbort(True)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)

    self.assertIsNone(try_job)
