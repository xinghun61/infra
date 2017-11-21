# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common import exceptions

from gae_libs.pipelines import pipeline

from model.flake.master_flake_analysis import MasterFlakeAnalysis

from pipelines.flake_failure.run_flake_try_job_pipeline import (
    RunFlakeTryJobPipeline)

from services.flake_failure import flake_try_job
from services.parameters import RunFlakeTryJobParameters

from waterfall.test import wf_testcase


class RunFlakeTryJobPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(flake_try_job, 'ScheduleFlakeTryJob', return_value='id')
  def testRunFlakeTryJobPipelineSuccess(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    revision = 'r1000'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        revision=revision,
        flake_cache_name=None,
        dimensions=[])

    try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
    try_job_id = try_job_pipeline.run(pipeline_input)
    self.assertEqual('id', try_job_id)

  @mock.patch.object(
      flake_try_job,
      'ScheduleFlakeTryJob',
      side_effect=exceptions.RetryException('error_reason', 'error_message'))
  def testRunFlakeTryJobPipelineRaise(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 's'
    test_name = 't'
    revision = 'r1000'

    analysis = MasterFlakeAnalysis.Create(master_name, builder_name,
                                          build_number, step_name, test_name)
    analysis.Save()

    pipeline_input = RunFlakeTryJobParameters(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        revision=revision,
        flake_cache_name=None,
        dimensions=[])

    try_job_pipeline = RunFlakeTryJobPipeline(pipeline_input)
    with self.assertRaises(pipeline.Retry):
      try_job_pipeline.run(pipeline_input)
