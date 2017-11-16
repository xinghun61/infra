# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from gae_libs.pipelines import pipeline
from gae_libs.pipeline_wrapper import BasePipeline
from common.waterfall import failure_type
from services import try_job as try_job_service
from services.test_failure import test_try_job
from waterfall import waterfall_config


class ScheduleTestTryJobPipeline(BasePipeline):
  """A pipeline for scheduling a new try job for failed test build."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self,
          master_name,
          builder_name,
          build_number,
          good_revision,
          bad_revision,
          suspected_revisions,
          cache_name,
          dimensions,
          targeted_tests,
          force_buildbot=False):
    """
    Args:
      master_name (str): the master name of a build.
      builder_name (str): the builder name of a build.
      build_number (int): the build number of a build.
      good_revision (str): the revision of the last passed build.
      bad__revision (str): the revision of the first failed build.
      suspected_revisions (list): a list of suspected revisions from heuristic.
      cache_name (str): A string to identify separate directories for different
          waterfall bots on the trybots.
      dimensions (list): A list of strings in the format
          ["key1:value1", "key2:value2"].
      targeted_tests (dict): a dict of reliable failed tests.
      force_buildbot (bool): Whether to force a run on buildbot slaves, ignoring
          swarmbucket configuration.

    Returns:
      build_id (str): id of the triggered try job.
    """

    properties = test_try_job.GetBuildProperties(
        master_name, builder_name, build_number, good_revision, bad_revision,
        suspected_revisions)

    if not targeted_tests:  # pragma: no cover
      logging.info('All tests are flaky, no try job will be triggered.')
      return

    additional_parameters = {'tests': targeted_tests}

    tryserver_mastername, tryserver_buildername = (
        waterfall_config.GetWaterfallTrybot(master_name, builder_name,
                                            force_buildbot))

    build_id, error = try_job_service.TriggerTryJob(
        master_name, builder_name, tryserver_mastername, tryserver_buildername,
        properties, additional_parameters,
        failure_type.GetDescriptionForFailureType(failure_type.TEST),
        cache_name, dimensions, self.pipeline_id)

    if error:  # pragma: no cover
      raise pipeline.Retry('Error "%s" occurred. Reason: "%s"' % (error.message,
                                                                  error.reason))
    try_job = try_job_service.UpdateTryJob(
        master_name, builder_name, build_number, build_id, failure_type.TEST)

    # Create a corresponding WfTryJobData entity to capture as much metadata as
    # early as possible.
    try_job_service.CreateTryJobData(build_id, try_job.key, False,
                                     bool(suspected_revisions),
                                     failure_type.TEST)

    return build_id
