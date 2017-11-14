# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from google.appengine.ext import ndb

from common.waterfall import buildbucket_client
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from model.wf_build import WfBuild
from services import try_job as try_job_service
from waterfall.flake.schedule_flake_try_job_pipeline import (
    ScheduleFlakeTryJobPipeline)
from waterfall.test import wf_testcase


class ScheduleFlakeTryJobPipelineTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(ScheduleFlakeTryJobPipelineTest, self).setUp()
    self.mock_select = mock.patch('waterfall.swarming_util.AssignWarmCacheHost')
    self.mock_select.start()

  def tearDown(self):
    self.mock_select.stop()
    super(ScheduleFlakeTryJobPipelineTest, self).tearDown()

  @mock.patch.object(try_job_service, 'buildbucket_client')
  def testScheduleFlakeTryJob(self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    step_name = 's'
    test_name = 't'
    git_hash = 'a1b2c3d4'
    build_id = '1'
    url = 'url'
    analysis_key = ndb.Key('key', 1)
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
            'url': url,
            'status': 'SCHEDULED',
        }
    }
    results = [(None, buildbucket_client.BuildbucketBuild(response['build']))]
    mock_module.TriggerTryJobs.return_value = results

    FlakeTryJob.Create(master_name, builder_name, step_name, test_name,
                       git_hash).put()

    try_job_pipeline = ScheduleFlakeTryJobPipeline()
    try_job_id = try_job_pipeline.run(master_name, builder_name, step_name,
                                      test_name, git_hash,
                                      analysis_key.urlsafe(), None, None)

    try_job = FlakeTryJob.Get(master_name, builder_name, step_name, test_name,
                              git_hash)
    try_job_data = FlakeTryJobData.Get(build_id)

    self.assertEqual(build_id, try_job_id)
    self.assertEqual(build_id, try_job.flake_results[-1]['try_job_id'])
    self.assertTrue(build_id in try_job.try_job_ids)
    self.assertEqual(try_job_data.try_job_key, try_job.key)
    self.assertEqual(analysis_key, try_job_data.analysis_key)
