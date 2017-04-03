# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from waterfall import buildbot
from waterfall import monitoring
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

  def _OnTryJobTriggered(
      self, try_job_type, master_name, builder_name):  # pragma: no cover.
    monitoring.try_jobs.increment(
        {
            'operation': 'trigger',
            'type': try_job_type,
            'master_name': master_name,
            'builder_name': builder_name
        })

  def _GetTrybot(self, master_name, builder_name):  # pragma: no cover.
    """Returns the master and builder on the tryserver to run the try job."""
    return waterfall_config.GetWaterfallTrybot(master_name, builder_name)

  def _TriggerTryJob(
      self, master_name, builder_name, properties, additional_parameters,
      try_job_type):

    tryserver_mastername, tryserver_buildername = self._GetTrybot(
        master_name, builder_name)

    try_job = buildbucket_client.TryJob(
        tryserver_mastername, tryserver_buildername, None, properties, [],
        additional_parameters)
    error, build = buildbucket_client.TriggerTryJobs([try_job])[0]

    self._OnTryJobTriggered(try_job_type, master_name, builder_name)

    if error:  # pragma: no cover
      raise pipeline.Retry(
          'Error "%s" occurred. Reason: "%s"' % (error.message, error.reason))

    return build.id

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, good_revision,
      bad_revision, try_job_type, suspected_revisions):
    raise NotImplementedError()
