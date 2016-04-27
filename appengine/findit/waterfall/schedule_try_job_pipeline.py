# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.pipeline_wrapper import BasePipeline
from common.pipeline_wrapper import pipeline
from common.waterfall import buildbucket_client
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall import buildbot
from waterfall import waterfall_config
from waterfall.try_job_type import TryJobType


class ScheduleTryJobPipeline(BasePipeline):
  """A pipeline for scheduling a new try job for current build."""

  def _GetBuildProperties(
      self, master_name, builder_name, build_number, good_revision,
      bad_revision, try_job_type, compile_targets, targeted_tests,
      suspected_revisions):
    properties = {
        'recipe': 'findit/chromium/%s' % try_job_type,
        'good_revision': good_revision,
        'bad_revision': bad_revision,
        'target_mastername': master_name,
        'referenced_build_url': buildbot.CreateBuildUrl(
            master_name, builder_name, build_number)
    }

    if try_job_type == TryJobType.COMPILE:
      properties['target_buildername'] = builder_name
      if compile_targets:
        properties['compile_targets'] = compile_targets
      if suspected_revisions:
        properties['suspected_revisions'] = suspected_revisions
    else:  # try_job_type is 'test'.
      properties['target_testername'] = builder_name
      assert targeted_tests
      properties['tests'] = targeted_tests

    return properties

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, good_revision,
      bad_revision, try_job_type, compile_targets, targeted_tests,
      suspected_revisions):
    tryserver_mastername, tryserver_buildername = (
        waterfall_config.GetTrybotForWaterfallBuilder(
            master_name, builder_name))

    properties = self._GetBuildProperties(
        master_name, builder_name, build_number, good_revision, bad_revision,
        try_job_type, compile_targets, targeted_tests, suspected_revisions)

    try_job = buildbucket_client.TryJob(
        tryserver_mastername, tryserver_buildername, None, properties, [])
    error, build = buildbucket_client.TriggerTryJobs([try_job])[0]

    if error:  # pragma: no cover
      raise pipeline.Retry(
          'Error "%s" occurred. Reason: "%s"' % (error.message, error.reason))

    try_job_result = WfTryJob.Get(master_name, builder_name, build_number)
    build_id = build.id

    if try_job_type == TryJobType.COMPILE:
      try_job_result.compile_results.append({'try_job_id': build_id})
    else:
      try_job_result.test_results.append({'try_job_id': build_id})
    try_job_result.try_job_ids.append(build_id)
    try_job_result.put()

    # Create a corresponding WfTryJobData entity to capture as much metadata as
    # early as possible.
    try_job_data = WfTryJobData.Create(build_id)
    try_job_data.master_name = master_name
    try_job_data.builder_name = builder_name
    try_job_data.build_number = build_number
    try_job_data.try_job_type = try_job_type
    try_job_data.has_compile_targets = bool(compile_targets)
    try_job_data.has_heuristic_results = bool(suspected_revisions)
    try_job_data.put()

    return build_id
