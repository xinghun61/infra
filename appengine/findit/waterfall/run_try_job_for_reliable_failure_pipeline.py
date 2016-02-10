# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import logging

from google.appengine.api import modules

from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from pipeline_wrapper import BasePipeline
from pipeline_wrapper import pipeline
from waterfall import try_job_pipeline
from waterfall.try_job_type import TryJobType


# TODO(chanli): Need to figure out why try-job-queue doesn't work.
TRY_JOB_PIPELINE_QUEUE_NAME = 'build-failure-analysis-queue'


def _GetReliableTargetedTests(targeted_tests, steps_statuses):
  """Uses SUCCESS/FAILURE statuses for each test to determine if it's reliable.

  For a test, if any run succeeded, this test is flaky and should not be
  included.
  """
  reliable_tests = defaultdict(list)
  for step_name, tests in targeted_tests.iteritems():
    if steps_statuses.get(step_name):
      tests_statuses = steps_statuses[step_name]
      for test in tests:
        if tests_statuses.get(test) and not tests_statuses[test].get('SUCCESS'):
          # Test has run but not succeeded, treats it as reliable failure.
          reliable_tests[step_name].append(test)
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
      steps_statuses):

    if try_job_type == TryJobType.TEST:
      targeted_tests = _GetReliableTargetedTests(
          targeted_tests, steps_statuses)
    if targeted_tests or try_job_type == TryJobType.COMPILE:
      new_try_job_pipeline = try_job_pipeline.TryJobPipeline(
          master_name, builder_name, build_number, good_revision,
          bad_revision, blame_list, try_job_type, compile_targets,
          targeted_tests)

      new_try_job_pipeline.target = (
          '%s.build-failure-analysis' % modules.get_current_version_name())
      new_try_job_pipeline.start()
      logging.info('Try-job was scheduled for build %s, %s, %s: %s',
                   master_name, builder_name, build_number,
                   new_try_job_pipeline.pipeline_status_path)
    else:  # pragma: no cover
      # No need to start try job, mark it as flaky.
      try_job_result = WfTryJob.Get(
          master_name, builder_name, build_number)
      if try_job_result:
        try_job_result.status = wf_analysis_status.FLAKY
        try_job_result.put()
      return
