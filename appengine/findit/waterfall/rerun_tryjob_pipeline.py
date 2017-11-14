# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from waterfall.monitor_try_job_pipeline import MonitorTryJobPipeline
from waterfall.schedule_compile_try_job_pipeline import (
    ScheduleCompileTryJobPipeline)
from waterfall.schedule_test_try_job_pipeline import (
    ScheduleTestTryJobPipeline)


class RerunTryJobPipeline(BasePipeline):
  """Re-runs a swarmbucket tryjob on buildbot for perf comparison."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, try_job_type,
          properties, additional_parameters, urlsafe_try_job_key):
    if try_job_type == failure_type.TEST:
      rerun = yield ScheduleTestTryJobPipeline(
          master_name,
          builder_name,
          build_number,
          properties['good_revision'],
          properties['bad_revision'],
          properties.get('suspected_revisions'),
          None,
          None,
          additional_parameters.get('tests'),
          force_buildbot=True)
    elif try_job_type == failure_type.COMPILE:
      rerun = yield ScheduleCompileTryJobPipeline(
          master_name,
          builder_name,
          build_number,
          properties['good_revision'],
          properties['bad_revision'],
          additional_parameters.get('compile_targets'),
          properties.get('suspected_revisions'),
          None,
          None,
          force_buildbot=True)
    else:
      raise pipeline.Abort(
          'Unsupported tryjob type %s' %
          failure_type.GetDescriptionForFailureType(try_job_type))
    yield MonitorTryJobPipeline(
        urlsafe_try_job_key,
        failure_type.GetDescriptionForFailureType(try_job_type), rerun)
