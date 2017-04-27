# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.waterfall import failure_type
from libs import time_util
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall.schedule_try_job_pipeline import ScheduleTryJobPipeline


class ScheduleCompileTryJobPipeline(ScheduleTryJobPipeline):
  """A pipeline for scheduling a new try job for failed compile build."""

  def _GetBuildProperties(
      self, master_name, builder_name, build_number, good_revision,
      bad_revision, try_job_type, suspected_revisions):
    properties = super(ScheduleCompileTryJobPipeline, self)._GetBuildProperties(
        master_name, builder_name, build_number, good_revision,
        bad_revision, try_job_type, suspected_revisions)
    properties['target_buildername'] = builder_name

    return properties

  def _CreateTryJobData(
      self, build_id, try_job_key, has_compile_targets, has_heuristic_results):
    try_job_data = WfTryJobData.Create(build_id)
    try_job_data.created_time = time_util.GetUTCNow()
    try_job_data.has_compile_targets = has_compile_targets
    try_job_data.has_heuristic_results = has_heuristic_results
    try_job_data.try_job_key = try_job_key
    try_job_data.try_job_type = failure_type.GetDescriptionForFailureType(
        failure_type.COMPILE)
    try_job_data.put()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, good_revision,
      bad_revision, try_job_type, compile_targets, suspected_revisions):
    """
    Args:
      master_name (str): the master name of a build.
      builder_name (str): the builder name of a build.
      build_number (int): the build number of a build.
      good_revision (str): the revision of the last passed build.
      bad__revision (str): the revision of the first failed build.
      try_job_type (int): type of the try job: COMPILE in this case.
      compile_targets (list): a list of failed output nodes.
      suspected_revisions (list): a list of suspected revisions from heuristic.

    Returns:
      build_id (str): id of the triggered try job.
    """

    properties = self._GetBuildProperties(
        master_name, builder_name, build_number, good_revision, bad_revision,
        try_job_type, suspected_revisions)
    additional_parameters = {'compile_targets': compile_targets}

    build_id = self._TriggerTryJob(
        master_name, builder_name, properties, additional_parameters,
        failure_type.GetDescriptionForFailureType(failure_type.COMPILE))

    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    try_job.compile_results.append({'try_job_id': build_id})
    try_job.try_job_ids.append(build_id)
    try_job.put()

    # Create a corresponding WfTryJobData entity to capture as much metadata as
    # early as possible.
    self._CreateTryJobData(
        build_id, try_job.key, bool(compile_targets), bool(suspected_revisions))

    return build_id
