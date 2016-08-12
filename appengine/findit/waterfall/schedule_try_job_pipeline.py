# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.pipeline_wrapper import BasePipeline
from common.pipeline_wrapper import pipeline
from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall import buildbot
from waterfall import waterfall_config


class ScheduleTryJobPipeline(BasePipeline):
  """A base pipeline for scheduling a new try job for current build."""

  def _GetBuildProperties(
      self, master_name, builder_name, build_number, good_revision,
      bad_revision, try_job_type, suspected_revisions):
    properties = {
        'recipe': 'findit/chromium/%s' % (
            failure_type.GetDescriptionForFailureType(try_job_type)),
        'good_revision': good_revision,
        'bad_revision': bad_revision,
        'target_mastername': master_name,
        'referenced_build_url': buildbot.CreateBuildUrl(
            master_name, builder_name, build_number)
    }

    if suspected_revisions:
      properties['suspected_revisions'] = suspected_revisions

    return properties

  def _TriggerTryJob(
      self, master_name, builder_name, properties, additional_parameters):
    tryserver_mastername, tryserver_buildername = (
        waterfall_config.GetTrybotForWaterfallBuilder(
            master_name, builder_name))

    try_job = buildbucket_client.TryJob(
        tryserver_mastername, tryserver_buildername, None, properties, [],
        additional_parameters)
    error, build = buildbucket_client.TriggerTryJobs([try_job])[0]

    if error:  # pragma: no cover
      raise pipeline.Retry(
          'Error "%s" occurred. Reason: "%s"' % (error.message, error.reason))

    return build.id

  def _CreateTryJobData(
      self, build_id, master_name, builder_name, build_number, try_job_type,
      has_compile_targets, has_heuristic_results):
    try_job_data = WfTryJobData.Create(build_id)
    try_job_data.master_name = master_name
    try_job_data.builder_name = builder_name
    try_job_data.build_number = build_number
    try_job_data.try_job_type = try_job_type
    try_job_data.has_compile_targets = has_compile_targets
    try_job_data.has_heuristic_results = has_heuristic_results
    try_job_data.put()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, good_revision,
      bad_revision, try_job_type, suspected_revisions):
    raise NotImplementedError()
