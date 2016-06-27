# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common.pipeline_wrapper import BasePipeline
from waterfall.process_swarming_task_result_pipeline import (
    ProcessSwarmingTaskResultPipeline)
from waterfall.run_try_job_for_reliable_failure_pipeline import (
    RunTryJobForReliableFailurePipeline)
from waterfall.trigger_swarming_task_pipeline import TriggerSwarmingTaskPipeline
from waterfall.try_job_type import TryJobType


_PRE_TEST_PREFIX = 'PRE_'


def _RemoveAnyPrefixes(tests):
  """Remove prefixes from test names.

  Args:
    tests (list): A list of tests, eg: ['suite1.PRE_test1', 'suite2.test2'].

  Returns:
    base_tests (list): A list of base tests, eg:
        ['suite1.test1', 'suite2.test2'].
  """
  base_tests = []
  for test in tests:
    test_name_start = test.find('.') if test.find('.') > -1 else 0
    test_suite = test[ : test_name_start]
    test_name = test[test_name_start + 1 : ]
    pre_position = test_name.find(_PRE_TEST_PREFIX)
    while pre_position == 0:
      test_name = test_name[len(_PRE_TEST_PREFIX):]
      pre_position = test_name.find(_PRE_TEST_PREFIX)
    base_tests.append(test_suite + '.' + test_name)
  return base_tests


class SwarmingTasksToTryJobPipeline(BasePipeline):
  """Root Pipeline to start swarming tasks and possible try job on the build."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, good_revision,
      bad_revision, blame_list, try_job_type, compile_targets=None,
      targeted_tests=None, suspected_cls=None, force_try_job=False):

    # A list contains tuples of step_names and classified_tests from
    # ProcessSwarmingTaskResultPipeline.
    # The format would be [('step1', {'flaky_tests': ['test1', ..], ..}), ..]
    classified_tests_by_step = []
    targeted_base_tests = {}

    if try_job_type == TryJobType.TEST:
      for step_name, tests in targeted_tests.iteritems():
        base_tests = _RemoveAnyPrefixes(tests)
        targeted_base_tests[step_name] = base_tests

        if not tests:  # Skip non-swarming tests.
          continue
        # Triggers swarming task for the base_tests.
        task_id = yield TriggerSwarmingTaskPipeline(
            master_name, builder_name, build_number, step_name, base_tests)
        step_future = yield ProcessSwarmingTaskResultPipeline(
            master_name, builder_name, build_number, step_name, task_id)
        logging_str = (
            'Swarming task was scheduled for build %s/%s/%s step %s') % (
                master_name, builder_name, build_number, step_name)
        logging.info(logging_str)
        classified_tests_by_step.append(step_future)

    # Waits until classified_tests_by_step are ready.
    yield RunTryJobForReliableFailurePipeline(
        master_name, builder_name, build_number, good_revision,
        bad_revision, blame_list, try_job_type, compile_targets,
        targeted_base_tests, suspected_cls, force_try_job,
        *classified_tests_by_step)
