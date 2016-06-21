# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import buildbucket_client
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall.schedule_try_job_pipeline import ScheduleTryJobPipeline
from waterfall.test import wf_testcase
from waterfall.try_job_type import TryJobType


class ScheduleTryjobPipelineTest(wf_testcase.WaterfallTestCase):

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
    build_number = 1

    expected_properties = {
        'recipe': 'findit/chromium/compile',
        'good_revision': 1,
        'bad_revision': 2,
        'target_mastername': master_name,
        'target_buildername': 'b',
        'referenced_build_url': ('https://build.chromium.org/p/%s/builders'
                                 '/%s/builds/%s') % (
                                     master_name, builder_name, build_number)
    }
    try_job_pipeline = ScheduleTryJobPipeline()
    properties = try_job_pipeline._GetBuildProperties(
        master_name, builder_name, build_number, 1, 2, TryJobType.COMPILE, None)

    self.assertEqual(properties, expected_properties)

  def testGetBuildPropertiesForTestFailure(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    expected_properties = {
        'recipe': 'findit/chromium/test',
        'good_revision': 1,
        'bad_revision': 2,
        'target_mastername': master_name,
        'target_testername': 'b',
        'referenced_build_url': ('https://build.chromium.org/p/%s/builders'
                                 '/%s/builds/%s') % (
                                     master_name, builder_name, build_number)
    }
    try_job_pipeline = ScheduleTryJobPipeline()
    properties = try_job_pipeline._GetBuildProperties(
        master_name, builder_name, build_number, 1, 2, TryJobType.TEST, None)

    self.assertEqual(properties, expected_properties)

  def testSuccessfullyScheduleNewTryJobForCompileWithSuspectedRevisions(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    build_id = '1'
    url = 'url'

    responses = [
        {
            'build': {
                'id': build_id,
                'url': url,
                'status': 'SCHEDULED',
            }
        }
    ]

    self._Mock_TriggerTryJobs(responses)

    WfTryJob.Create(master_name, builder_name, build_number).put()

    try_job_pipeline = ScheduleTryJobPipeline()
    try_job_id = try_job_pipeline.run(
        master_name, builder_name, build_number, good_revision, bad_revision,
        TryJobType.COMPILE, None, None, ['r5'])

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Get(build_id)

    expected_try_job_id = '1'
    self.assertEqual(expected_try_job_id, try_job_id)
    self.assertEqual(
        expected_try_job_id, try_job.compile_results[-1]['try_job_id'])
    self.assertTrue(expected_try_job_id in try_job.try_job_ids)
    self.assertIsNotNone(try_job_data)
    self.assertEqual(try_job_data.master_name, master_name)
    self.assertEqual(try_job_data.builder_name, builder_name)
    self.assertEqual(try_job_data.build_number, build_number)
    self.assertEqual(try_job_data.try_job_type, TryJobType.COMPILE)
    self.assertFalse(try_job_data.has_compile_targets)
    self.assertTrue(try_job_data.has_heuristic_results)

  def testSuccessfullyScheduleNewTryJobForTest(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}
    build_id = '1'

    responses = [
        {
            'build': {
                'id': build_id,
                'url': 'url',
                'status': 'SCHEDULED',
            }
        }
    ]
    self._Mock_TriggerTryJobs(responses)

    WfTryJob.Create(master_name, builder_name, build_number).put()

    try_job_pipeline = ScheduleTryJobPipeline()
    try_job_id = try_job_pipeline.run(
        master_name, builder_name, build_number, good_revision, bad_revision,
        TryJobType.TEST, None, targeted_tests, None)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertEqual(try_job_id, build_id)
    self.assertEqual(try_job.test_results[-1]['try_job_id'], build_id)
    self.assertIsNotNone(try_job_data)
    self.assertEqual(try_job_data.master_name, master_name)
    self.assertEqual(try_job_data.builder_name, builder_name)
    self.assertEqual(try_job_data.build_number, build_number)
    self.assertEqual(try_job_data.try_job_type, TryJobType.TEST)
    self.assertFalse(try_job_data.has_compile_targets)
    self.assertFalse(try_job_data.has_heuristic_results)
