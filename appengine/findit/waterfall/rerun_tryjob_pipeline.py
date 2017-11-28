# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from gae_libs.pipelines import pipeline
from gae_libs.pipeline_wrapper import BasePipeline
from pipelines.compile_failure.run_compile_try_job_pipeline import (
    RunCompileTryJobPipeline)
from pipelines.test_failure.schedule_test_try_job_pipeline import (
    ScheduleTestTryJobPipeline)
from services.parameters import BuildKey
from services.parameters import RunCompileTryJobParameters
from services.parameters import RunTestTryJobParameters
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline


class RerunTryJobPipeline(BasePipeline):
  """Re-runs a swarmbucket tryjob on buildbot for perf comparison."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, try_job_type,
          properties, additional_parameters, urlsafe_try_job_key):
    if try_job_type == failure_type.TEST:
      pipeline_input = RunTestTryJobParameters(
          build_key=BuildKey(
              master_name=master_name,
              builder_name=builder_name,
              build_number=build_number),
          good_revision=properties['good_revision'],
          bad_revision=properties['bad_revision'],
          suspected_revisions=properties.get('suspected_revisions'),
          targeted_tests=additional_parameters.get('tests'),
          cache_name=None,
          dimensions=[],
          force_buildbot=True,
          urlsafe_try_job_key=urlsafe_try_job_key)
      rerun = yield ScheduleTestTryJobPipeline(pipeline_input)
      yield MonitorTryJobPipeline(
          urlsafe_try_job_key,
          failure_type.GetDescriptionForFailureType(try_job_type), rerun)

    elif try_job_type == failure_type.COMPILE:
      pipeline_input = RunCompileTryJobParameters(
          build_key=BuildKey(
              master_name=master_name,
              builder_name=builder_name,
              build_number=build_number),
          good_revision=properties['good_revision'],
          bad_revision=properties['bad_revision'],
          compile_targets=additional_parameters.get('compile_targets'),
          suspected_revisions=properties.get('suspected_revisions'),
          cache_name=None,
          dimensions=[],
          force_buildbot=True,
          urlsafe_try_job_key=urlsafe_try_job_key)
      yield RunCompileTryJobPipeline(pipeline_input)
    else:
      raise pipeline.Abort(
          'Unsupported tryjob type %s' %
          failure_type.GetDescriptionForFailureType(try_job_type))
