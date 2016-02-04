# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from common import buildbucket_client
from model.wf_try_job import WfTryJob
from waterfall import waterfall_config
from waterfall.schedule_try_job_pipeline import ScheduleTryJobPipeline
from waterfall.try_job_type import TryJobType


class ScheduleTryjobPipelineTest(testing.AppengineTestCase):

  def _Mock_GetTrybotForWaterfallBuilder(self, *_):
    def MockedGetTrybotForWaterfallBuilder(*_):
      return 'linux_chromium_variable', 'master.tryserver.chromium.linux'
    self.mock(waterfall_config, 'GetTrybotForWaterfallBuilder',
              MockedGetTrybotForWaterfallBuilder)

  def _Mock_TriggerTryJobs(self, responses):
    def MockedTriggerTryJobs(*_):
      results = []
      for response in responses:
        if response.get('error'):  # pragma: no cover
          results.append((
              buildbucket_client.BuildbucketError(response['error']), None))
        else:
          results.append((
              None, buildbucket_client.BuildbucketBuild(response['build'])))
      return results
    self.mock(buildbucket_client, 'TriggerTryJobs', MockedTriggerTryJobs)

  def testGetBuildPropertiesWithCompileTargets(self):
    master_name = 'm'
    builder_name = 'b'
    compile_targets = ['a.exe']

    expected_properties = {
        'recipe': 'findit/chromium/compile',
        'good_revision': 1,
        'bad_revision': 2,
        'target_mastername': master_name,
        'target_buildername': 'b',
        'compile_targets': compile_targets
    }
    try_job_pipeline = ScheduleTryJobPipeline()
    properties = try_job_pipeline._GetBuildProperties(
        master_name, builder_name, 1, 2, TryJobType.COMPILE,
        compile_targets, None)

    self.assertEqual(properties, expected_properties)

  def testGetBuildPropertiesForTestFailure(self):
    master_name = 'm'
    builder_name = 'b'
    targeted_tests = {'a': []}

    expected_properties = {
        'recipe': 'findit/chromium/test',
        'good_revision': 1,
        'bad_revision': 2,
        'target_mastername': master_name,
        'target_testername': 'b',
        'tests': targeted_tests
    }
    try_job_pipeline = ScheduleTryJobPipeline()
    properties = try_job_pipeline._GetBuildProperties(
        master_name, builder_name, 1, 2, TryJobType.TEST,
        None, targeted_tests)

    self.assertEqual(properties, expected_properties)

  def testSuccessfullyScheduleNewTryJobForCompile(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
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

    WfTryJob.Create(master_name, builder_name, build_number).put()

    try_job_pipeline = ScheduleTryJobPipeline()
    try_job_id = try_job_pipeline.run(
        master_name, builder_name, build_number, good_revision, bad_revision,
        TryJobType.COMPILE, None, None)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    expected_try_job_id = '1'
    self.assertEqual(expected_try_job_id, try_job_id)
    self.assertEqual(
        expected_try_job_id, try_job.compile_results[-1]['try_job_id'])
    self.assertTrue(expected_try_job_id in try_job.try_job_ids)

  def testSuccessfullyScheduleNewTryJobForTest(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}

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

    WfTryJob.Create(master_name, builder_name, build_number).put()

    try_job_pipeline = ScheduleTryJobPipeline()
    try_job_id = try_job_pipeline.run(
        master_name, builder_name, build_number, good_revision, bad_revision,
        TryJobType.TEST, None, targeted_tests)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual('1', try_job_id)
    self.assertEqual('1', try_job.test_results[-1]['try_job_id'])
