# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from common.pipeline_wrapper import BasePipeline

from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.flake.flake_swarming_task import FlakeSwarmingTask
from waterfall.process_base_swarming_task_result_pipeline import (
    ProcessBaseSwarmingTaskResultPipeline)


class ProcessFlakeSwarmingTaskResultPipeline(
    ProcessBaseSwarmingTaskResultPipeline):
  """A pipeline for monitoring swarming task and processing task result.

  This pipeline waits for result for a swarming task and processes the result to
  generate a dict for statuses for each test run.
  """

  # Arguments number differs from overridden method - pylint: disable=W0221
  def _CheckTestsRunStatuses(self, output_json, master_name,
                             builder_name, build_number, step_name,
                             master_build_number, test_name):
    """Checks result status for each test run and saves the numbers accordingly.

    Args:
      output_json (dict): A dict of all test results in the swarming task.
      master_name (string): Name of master of swarming rerun.
      builder_name (dict): Name of builder of swarming rerun.
      build_number (int): Build Number of swarming rerun.
      step_name (dict): Name of step of swarming rerun.
      master_build_number (int): Build number of corresponding mfa
      test_name (string): Name of test of swarming rerun

    Returns:
      tests_statuses (dict): A dict of different statuses for each test.

    Currently for each test, we are saving number of total runs,
    number of succeeded runs and number of failed runs.
    """

    tests_statuses = defaultdict(lambda: defaultdict(int))

    if not output_json:
      return tests_statuses

    for iteration in output_json.get('per_iteration_data'):
      for name, test_runs in iteration.iteritems():
        tests_statuses[name]['total_run'] += len(test_runs)
        for test_run in test_runs:
          tests_statuses[name][test_run['status']] += 1

    # Should query by test name, because some test has dependencies which
    # are also run, like TEST and PRE_TEST in browser_tests.
    tries = tests_statuses.get(test_name, {}).get('total_run', 0)
    successes = tests_statuses.get(test_name, {}).get('SUCCESS', 0)

    if tries > 0:
      success_rate = successes * 1.0 / tries
    else:
      success_rate = -1 # Special value to indicate test is not existing.

    master_flake_analysis = MasterFlakeAnalysis.Get(master_name, builder_name,
                                                    master_build_number,
                                                    step_name, test_name)
    flake_swarming_task = FlakeSwarmingTask.Get(
        master_name, builder_name, build_number, step_name, test_name)

    master_flake_analysis.build_numbers.append(build_number)
    master_flake_analysis.success_rates.append(success_rate)
    flake_swarming_task.tries = tries
    flake_swarming_task.successes = successes
    flake_swarming_task.put()
    master_flake_analysis.put()
    return tests_statuses

  def _GetArgs(self, master_name, builder_name, build_number,
               step_name, *args):
    master_build_number = args[0]
    test_name = args[1]
    return (master_name, builder_name, build_number, step_name,
            master_build_number, test_name)

  # Unused Argument - pylint: disable=W0612,W0613
  def _GetSwarmingTask(self, master_name, builder_name, build_number,
                       step_name, master_build_number, test_name):
    # Get the appropriate kind of Swarming Task (Flake).
    return FlakeSwarmingTask.Get(master_name, builder_name,
                                 build_number, step_name, test_name)
