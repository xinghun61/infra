# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from model.wf_build import WfBuild
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from services import try_job as try_job_service
from waterfall.schedule_test_try_job_pipeline import (
    ScheduleTestTryJobPipeline)
from waterfall.test import wf_testcase


class ScheduleTestTryjobPipelineTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(ScheduleTestTryjobPipelineTest, self).setUp()
    self.mock_select = mock.patch('waterfall.swarming_util.AssignWarmCacheHost')
    self.mock_select.start()

  def tearDown(self):
    self.mock_select.stop()
    super(ScheduleTestTryjobPipelineTest, self).tearDown()

  @mock.patch.object(try_job_service, 'buildbucket_client')
  def testSuccessfullyScheduleNewTryJobForTest(self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}
    build_id = '1'
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.data = {
        'properties': {
            'parent_mastername': 'pm',
            'parent_buildername': 'pb'
        }
    }
    build.put()

    response = {
        'build': {
            'id': build_id,
            'url': 'url',
            'status': 'SCHEDULED',
        }
    }
    results = [(None, buildbucket_client.BuildbucketBuild(response['build']))]
    mock_module.TriggerTryJobs.return_value = results

    WfTryJob.Create(master_name, builder_name, build_number).put()

    try_job_pipeline = ScheduleTestTryJobPipeline()
    try_job_id = try_job_pipeline.run(master_name, builder_name, build_number,
                                      good_revision, bad_revision, None, None,
                                      None, targeted_tests)

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(try_job_id, build_id)
    self.assertEqual(try_job.test_results[-1]['try_job_id'], build_id)

    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNotNone(try_job_data)
    self.assertEqual(try_job_data.master_name, master_name)
    self.assertEqual(try_job_data.builder_name, builder_name)
    self.assertEqual(try_job_data.build_number, build_number)
    self.assertEqual(
        try_job_data.try_job_type,
        failure_type.GetDescriptionForFailureType(failure_type.TEST))
    self.assertFalse(try_job_data.has_compile_targets)
    self.assertFalse(try_job_data.has_heuristic_results)
