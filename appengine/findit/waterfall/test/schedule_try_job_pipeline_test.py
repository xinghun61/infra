# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from waterfall import schedule_try_job_pipeline
from waterfall.schedule_try_job_pipeline import ScheduleTryJobPipeline
from waterfall.test import wf_testcase


class ScheduleTryjobPipelineTest(wf_testcase.WaterfallTestCase):

  def testGetBuildPropertiesWithSuspectedRevision(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    expected_properties = {
        'recipe': 'findit/chromium/compile',
        'good_revision': 1,
        'bad_revision': 2,
        'target_mastername': master_name,
        'referenced_build_url': ('https://build.chromium.org/p/%s/builders'
                                 '/%s/builds/%s') % (
                                     master_name, builder_name, build_number),
        'suspected_revisions': ['rev']
    }
    try_job_pipeline = ScheduleTryJobPipeline()
    properties = try_job_pipeline._GetBuildProperties(
        master_name, builder_name, build_number, 1, 2, failure_type.COMPILE,
        ['rev'])

    self.assertEqual(properties, expected_properties)

  def testGetBuildPropertiesNoSuspectedRevision(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    expected_properties = {
        'recipe': 'findit/chromium/test',
        'good_revision': 1,
        'bad_revision': 2,
        'target_mastername': master_name,
        'referenced_build_url': ('https://build.chromium.org/p/%s/builders'
                                 '/%s/builds/%s') % (
                                     master_name, builder_name, build_number)
    }
    try_job_pipeline = ScheduleTryJobPipeline()
    properties = try_job_pipeline._GetBuildProperties(
        master_name, builder_name, build_number, 1, 2, failure_type.TEST, None)

    self.assertEqual(properties, expected_properties)

  @mock.patch.object(schedule_try_job_pipeline, 'buildbucket_client')
  def testTriggerTryJob(self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    response = {
        'build': {
            'id': '1',
            'url': 'url',
            'status': 'SCHEDULED',
        }
    }
    results = [(None, buildbucket_client.BuildbucketBuild(response['build']))]
    mock_module.TriggerTryJobs.return_value = results

    try_job_pipeline = ScheduleTryJobPipeline()
    build_id = try_job_pipeline._TriggerTryJob(
        master_name, builder_name, {}, [])

    self.assertEqual(build_id, '1')
