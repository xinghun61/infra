# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import DataPoint
from model.flake.master_flake_analysis import MasterFlakeAnalysis
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
                             master_build_number, test_name, version_number):
    """Checks result status for each test run and saves the numbers accordingly.

    Args:
      output_json (dict): A dict of all test results in the swarming task.
      master_name (string): Name of master of swarming rerun.
      builder_name (dict): Name of builder of swarming rerun.
      build_number (int): Build Number of swarming rerun.
      step_name (dict): Name of step of swarming rerun.
      master_build_number (int): Build number of corresponding mfa.
      test_name (string): Name of test of swarming rerun.
      version_number (int): The version to save analysis results and ` to.

    Returns:
      tests_statuses (dict): A dict of different statuses for each test.

    Currently for each test, we are saving number of total runs,
    number of succeeded runs and number of failed runs.
    """

    tests_statuses = super(ProcessFlakeSwarmingTaskResultPipeline,
                           self)._CheckTestsRunStatuses(output_json)

    # Should query by test name, because some test has dependencies which
    # are also run, like TEST and PRE_TEST in browser_tests.
    tries = tests_statuses.get(test_name, {}).get('total_run', 0)
    successes = tests_statuses.get(test_name, {}).get('SUCCESS', 0)

    if tries > 0:
      pass_rate = successes * 1.0 / tries
    else:
      pass_rate = -1  # Special value to indicate test is not existing.

    master_flake_analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, master_build_number, step_name, test_name,
        version=version_number)
    logging.info(
        'Updating MasterFlakeAnalysis data %s/%s/%s/%s/%s',
        master_name, builder_name, master_build_number, step_name, test_name)
    logging.info('MasterFlakeAnalysis %s version %s',
                 master_flake_analysis, master_flake_analysis.version_number)

    data_point = DataPoint()
    data_point.build_number = build_number
    data_point.pass_rate = pass_rate
    master_flake_analysis.data_points.append(data_point)

    flake_swarming_task = FlakeSwarmingTask.Get(
        master_name, builder_name, build_number, step_name, test_name)
    flake_swarming_task.tries = tries
    flake_swarming_task.successes = successes
    flake_swarming_task.put()

    results = flake_swarming_task.GetFlakeSwarmingTaskData()
    # TODO(lijeffrey): Determine whether or not this flake swarming task
    # was a cache hit (already ran results for more iterations than were
    # requested) and update results['cache_hit'] accordingly.
    master_flake_analysis.swarming_rerun_results.append(results)
    master_flake_analysis.put()

    return tests_statuses

  def _GetArgs(self, master_name, builder_name, build_number,
               step_name, *args):
    master_build_number = args[0]
    test_name = args[1]
    version_number = args[2]
    return (master_name, builder_name, build_number, step_name,
            master_build_number, test_name, version_number)

  # Unused Argument - pylint: disable=W0612,W0613
  # Arguments number differs from overridden method - pylint: disable=W0221
  def _GetSwarmingTask(self, master_name, builder_name, build_number,
                       step_name, master_build_number, test_name, _):
    # Gets the appropriate kind of swarming task (FlakeSwarmingTask).
    return FlakeSwarmingTask.Get(master_name, builder_name, build_number,
                                 step_name, test_name)
