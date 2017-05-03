# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from model.wf_build import WfBuild
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall import schedule_try_job_pipeline
from waterfall.schedule_compile_try_job_pipeline import (
    ScheduleCompileTryJobPipeline)
from waterfall.test import wf_testcase


class ScheduleCompileTryJobPipelineTest(wf_testcase.WaterfallTestCase):

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
        'referenced_build_url': (
            'https://luci-milo.appspot.com/buildbot/%s/%s/%s') % (
                master_name, builder_name, build_number)
    }
    try_job_pipeline = ScheduleCompileTryJobPipeline()
    properties = try_job_pipeline._GetBuildProperties(
        master_name, builder_name, build_number, 1, 2,
        failure_type.COMPILE, None)

    self.assertEqual(properties, expected_properties)

  @mock.patch.object(schedule_try_job_pipeline, 'buildbucket_client')
  def testSuccessfullyScheduleNewTryJobForCompileWithSuspectedRevisions(
      self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    build_id = '1'
    url = 'url'
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.data = {'properties': {'parent_mastername': 'pm',
                                 'parent_buildername': 'pb'}}
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

    WfTryJob.Create(master_name, builder_name, build_number).put()

    try_job_pipeline = ScheduleCompileTryJobPipeline()
    try_job_id = try_job_pipeline.run(
        master_name, builder_name, build_number, good_revision, bad_revision,
        failure_type.COMPILE, None, ['r5'], None, None)

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
    self.assertEqual(
        try_job_data.try_job_type,
        failure_type.GetDescriptionForFailureType(failure_type.COMPILE))
    self.assertFalse(try_job_data.has_compile_targets)
    self.assertTrue(try_job_data.has_heuristic_results)
