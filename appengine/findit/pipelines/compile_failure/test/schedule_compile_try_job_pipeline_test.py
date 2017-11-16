# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import exceptions
from gae_libs.pipelines import pipeline
from pipelines.compile_failure.schedule_compile_try_job_pipeline import (
    ScheduleCompileTryJobPipeline)
from services.compile_failure import compile_try_job
from services.parameters import BuildKey
from services.parameters import ScheduleCompileTryJobParameters
from waterfall.test import wf_testcase


class ScheduleCompileTryJobPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(compile_try_job, 'ScheduleCompileTryJob', return_value='1')
  def testSuccessfullyScheduleNewTryJobForCompileWithSuspectedRevisions(
      self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'

    pipeline_input = ScheduleCompileTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision=good_revision,
        bad_revision=bad_revision,
        suspected_revisions=['r5'],
        cache_name=None,
        dimensions=[],
        force_buildbot=False,
        compile_targets=[])
    try_job_pipeline = ScheduleCompileTryJobPipeline(pipeline_input)
    try_job_id = try_job_pipeline.run(pipeline_input)

    self.assertEqual('1', try_job_id)

  @mock.patch.object(
      compile_try_job,
      'ScheduleCompileTryJob',
      side_effect=exceptions.RetryException('error_reason', 'error_message'))
  def testScheduleNewTryJobForCompileRaiseRetry(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223
    good_revision = 'rev1'
    bad_revision = 'rev2'

    pipeline_input = ScheduleCompileTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision=good_revision,
        bad_revision=bad_revision,
        suspected_revisions=['r5'],
        cache_name=None,
        dimensions=[],
        force_buildbot=False,
        compile_targets=[])
    try_job_pipeline = ScheduleCompileTryJobPipeline(pipeline_input)
    with self.assertRaises(pipeline.Retry):
      try_job_pipeline.run(pipeline_input)
