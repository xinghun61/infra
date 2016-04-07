# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import logging

from common import appengine_util
from common import constants
from model import analysis_status
from model.wf_try_job import WfTryJob
from pipeline_wrapper import BasePipeline
from pipeline_wrapper import pipeline
from waterfall import try_job_pipeline
from waterfall.try_job_type import TryJobType


def _GetReliableTargetedTests(targeted_tests, classified_tests_by_step):
  """Returns a dict containing a list of reliable tests for each failed step."""
  reliable_tests = defaultdict(list)
  for step_name, tests in targeted_tests.iteritems():
    if step_name in classified_tests_by_step:  # Swarming step.
      # If the step is swarming but there is no result for it, it's highly
      # likely that there is some error with the task.
      # Thus skip this step for no insights from task to avoid false positive.
      step_name_no_platform = classified_tests_by_step[step_name][0]
      classified_tests = classified_tests_by_step[step_name][1]

      for test in tests:
        if (test in classified_tests.get('reliable_tests', [])):
          reliable_tests[step_name_no_platform].append(test)
    else:  # Non-swarming step, includes it directly.
      reliable_tests[step_name] = []
  return reliable_tests


class RunTryJobForReliableFailurePipeline(BasePipeline):
  """A pipeline to trigger try job for reliable failures.

  Processes result from SwarmingTaskPipeline and start TryJobPipeline if there
  are reliable test failures.
  Starts TryJobPipeline directly for compile failure.
  """

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, good_revision,
      bad_revision, blame_list, try_job_type, compile_targets, targeted_tests,
      *classified_tests_by_step):
    """
    Args:
      master_name (str): Name of the master.
      builder_name (str): Name of the builder.
      build_number (int): Number of the current failed build.
      good_revision (str): Revision of last green build.
      bad_revision (str): Revision of current build.
      blame_list (list): A list of revisions between above 2 revisions.
      try_job_type (str): Type of the try job ('compile' or 'test').
      compile_targets (list): A list of failed targets for compile failure.
      targeted_tests (dict): A dict of failed tests for test failure.
      *classified_tests_by_step (list): A list of tuples of step_name and
          classified_tests. The format is like:
          [('step1', {'flaky_tests': ['test1', ..], ..}), ..]
    """
    if try_job_type == TryJobType.TEST:
      targeted_tests = _GetReliableTargetedTests(
          targeted_tests, dict(classified_tests_by_step))
    if targeted_tests or try_job_type == TryJobType.COMPILE:
      new_try_job_pipeline = try_job_pipeline.TryJobPipeline(
          master_name, builder_name, build_number, good_revision,
          bad_revision, blame_list, try_job_type, compile_targets,
          targeted_tests)

      new_try_job_pipeline.target = appengine_util.GetTargetNameForModule(
          constants.WATERFALL_BACKEND)
      new_try_job_pipeline.start(queue_name=constants.WATERFALL_TRY_JOB_QUEUE)
      logging.info('Try-job was scheduled for build %s, %s, %s: %s',
                   master_name, builder_name, build_number,
                   new_try_job_pipeline.pipeline_status_path)
    else:  # pragma: no cover
      # No need to start try job, mark it as skipped.
      try_job_result = WfTryJob.Get(
          master_name, builder_name, build_number)
      if try_job_result:
        try_job_result.status = analysis_status.SKIPPED
        try_job_result.put()
      return
