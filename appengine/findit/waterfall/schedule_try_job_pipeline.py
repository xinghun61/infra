# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import buildbucket_client
from model.wf_try_job import WfTryJob
from pipeline_wrapper import BasePipeline
from pipeline_wrapper import pipeline
from waterfall import waterfall_config


class ScheduleTryJobPipeline(BasePipeline):
  """A pipeline for scheduling a new try job for current build."""

  def _getBuildProperties(self, recipe, master_name, builder_name,
                          good_revision, bad_revision, compile_targets):

    properties = {
        'recipe': recipe,
        'good_revision': good_revision,
        'bad_revision': bad_revision,
        'target_mastername': master_name,
        'target_buildername': builder_name
    }

    if compile_targets:
      properties['compile_targets'] = compile_targets

    return properties

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number,
      good_revision, bad_revision, compile_targets):
    tryserver_mastername, tryserver_buildername = (
        waterfall_config.GetTrybotForWaterfallBuilder(
            master_name, builder_name))

    recipe = 'findit/chromium/compile'
    properties = self._getBuildProperties(
        recipe, master_name, builder_name, good_revision, bad_revision,
        compile_targets)

    try_job = buildbucket_client.TryJob(
        tryserver_mastername, tryserver_buildername, None, properties, [])
    error, build = buildbucket_client.TriggerTryJobs([try_job])[0]

    if error:  # pragma: no cover
      raise pipeline.Retry(
          'Error "%s" occurred. Reason: "%s"' % (error.message, error.reason))

    try_job_result = WfTryJob.Get(master_name, builder_name, build_number)
    try_job_result.compile_results.append({'try_job_id': build.id})
    try_job_result.try_job_ids.append(build.id)
    try_job_result.put()

    return build.id
