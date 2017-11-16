# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock

from common import exceptions
from gae_libs.pipelines import pipeline
from pipelines.test_failure.schedule_test_try_job_pipeline import (
    ScheduleTestTryJobPipeline)
from services.parameters import BuildKey
from services.parameters import ScheduleTestTryJobParameters
from services.test_failure import test_try_job
from waterfall.test import wf_testcase


class ScheduleTestTryjobPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(test_try_job, 'ScheduleTestTryJob', return_value='1')
  def testSuccessfullyScheduleNewTryJobForTest(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}

    pipeline_input = ScheduleTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision=bad_revision,
        good_revision=good_revision,
        suspected_revisions=[],
        targeted_tests=targeted_tests,
        dimensions=[],
        cache_name=None,
        force_buildbot=False)

    try_job_pipeline = ScheduleTestTryJobPipeline(pipeline_input)
    try_job_id = try_job_pipeline.run(pipeline_input)
    self.assertEqual('1', try_job_id)

  @mock.patch.object(
      test_try_job,
      'ScheduleTestTryJob',
      side_effect=exceptions.RetryException('error_reason', 'error_message'))
  def testScheduleNewTryJobForTestRaise(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}

    pipeline_input = ScheduleTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision=bad_revision,
        good_revision=good_revision,
        suspected_revisions=[],
        targeted_tests=targeted_tests,
        dimensions=[],
        cache_name=None,
        force_buildbot=False)

    try_job_pipeline = ScheduleTestTryJobPipeline(pipeline_input)
    with self.assertRaises(pipeline.Retry):
      try_job_pipeline.run(pipeline_input)
