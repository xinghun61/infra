# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import appengine_util
from common import constants
from common.pipeline_wrapper import BasePipeline

from model import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import waterfall_config
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)


class RecursiveFlakePipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, run_build_number, step_name,
          test_name, master_build_number, flakiness_algorithm_results_dict,
          queue_name=constants.DEFAULT_QUEUE):
    """Pipeline to determine the regression range of a flaky test.

    Args:
      master_name (str): The master name.
      builder_name (str): The builder name.
      run_build_number (int): The build number of the current swarming rerun.
      step_name (str): The step name.
      test_name (str): The test name.
      master_build_number (int): The build number of the Master_Flake_analysis.
      flakiness_algorithm_results_dict (dict): A dictionary used by
        NextBuildNumberPipeline
      queue_name (str): Which queue to run on.

    Returns:
      A dict of lists for reliable/flaky tests.
    """
    master = MasterFlakeAnalysis.Get(master_name, builder_name,
                                     master_build_number, step_name, test_name)
    if master.status != analysis_status.RUNNING:  # pragma: no branch
      master.status = analysis_status.RUNNING
      master.put()

    # Call trigger pipeline (flake style).
    task_id = yield TriggerFlakeSwarmingTaskPipeline(
        master_name, builder_name, run_build_number, step_name, [test_name])
    # Pass the trigger pipeline into a process pipeline.
    test_result_future = yield ProcessFlakeSwarmingTaskResultPipeline(
        master_name, builder_name, run_build_number,
        step_name, task_id, master_build_number, test_name)
    yield NextBuildNumberPipeline(
        master_name, builder_name, master_build_number, run_build_number,
        step_name, test_name, test_result_future, queue_name,
        flakiness_algorithm_results_dict)


def get_next_run(master, flakiness_algorithm_results_dict):
  # A description of this algorithm can be found at:
  # https://docs.google.com/document/d/1wPYFZ5OT998Yn7O8wGDOhgfcQ98mknoX13AesJaS6ig/edit
  # Get the last result.
  last_result = master.success_rates[-1]
  cur_run = min(master.build_numbers)
  flake_settings = waterfall_config.GetCheckFlakeSettings()
  lower_flake_threshold = flake_settings.get('lower_flake_threshold')
  upper_flake_threshold = flake_settings.get('upper_flake_threshold')
  max_stable_in_a_row = flake_settings.get('max_stable_in_a_row')
  max_flake_in_a_row = flake_settings.get('max_flake_in_a_row')

  if last_result < 0: # Test doesn't exist in the current build number.
    flakiness_algorithm_results_dict['stable_in_a_row'] += 1
    flakiness_algorithm_results_dict['stabled_out'] = True
    flakiness_algorithm_results_dict['flaked_out'] = True
    flakiness_algorithm_results_dict['lower_boundary_result'] = 'STABLE'

    lower_boundary = master.build_numbers[
        -flakiness_algorithm_results_dict['stable_in_a_row']]

    flakiness_algorithm_results_dict['lower_boundary'] = lower_boundary
    flakiness_algorithm_results_dict['sequential_run_index'] += 1
    return lower_boundary + 1
  elif (last_result < lower_flake_threshold or
      last_result > upper_flake_threshold):  # Stable result.
    flakiness_algorithm_results_dict['stable_in_a_row'] += 1
    if (flakiness_algorithm_results_dict['stable_in_a_row'] >
        max_stable_in_a_row):  # Identified a stable region.
      flakiness_algorithm_results_dict['stabled_out'] = True
    if (flakiness_algorithm_results_dict['stabled_out'] and
        not flakiness_algorithm_results_dict['flaked_out']):
      # Identified a candidate for the upper boundary.
      # Earliest stable point to the right of a flaky region.
      flakiness_algorithm_results_dict['upper_boundary'] = cur_run
      flakiness_algorithm_results_dict['lower_boundary'] = None
    elif (flakiness_algorithm_results_dict['flaked_out'] and
          not flakiness_algorithm_results_dict['stabled_out'] and
          not flakiness_algorithm_results_dict['lower_boundary']):
      # Identified a candidate for the lower boundary.
      # Latest stable point to the left of a flaky region.
      flakiness_algorithm_results_dict['lower_boundary'] = cur_run
      flakiness_algorithm_results_dict['lower_boundary_result'] = 'STABLE'
    flakiness_algorithm_results_dict['flakes_in_a_row'] = 0
    step_size = flakiness_algorithm_results_dict['stable_in_a_row'] + 1
    return cur_run - step_size
  else:
    # Flaky result.
    flakiness_algorithm_results_dict['flakes_in_a_row'] += 1
    if (flakiness_algorithm_results_dict['flakes_in_a_row'] >
        max_flake_in_a_row):  # Identified a flaky region.
      flakiness_algorithm_results_dict['flaked_out'] = True
    if (flakiness_algorithm_results_dict['flaked_out'] and
        not flakiness_algorithm_results_dict['stabled_out']):
      # Identified a candidate for the upper boundary.
      # Earliest flaky point to the right of a stable region.
      flakiness_algorithm_results_dict['upper_boundary'] = cur_run
      flakiness_algorithm_results_dict['lower_boundary'] = None
    elif (flakiness_algorithm_results_dict['stabled_out'] and
          not flakiness_algorithm_results_dict['flaked_out'] and
          not flakiness_algorithm_results_dict['lower_boundary']):
      # Identified a candidate for the lower boundary.
      # Latest flaky point to the left of a stable region.
      flakiness_algorithm_results_dict['lower_boundary'] = cur_run
      flakiness_algorithm_results_dict['lower_boundary_result'] = 'FLAKE'
    flakiness_algorithm_results_dict['stable_in_a_row'] = 0
    step_size = flakiness_algorithm_results_dict['flakes_in_a_row'] + 1
    return cur_run - step_size


def sequential_next_run(master, flakiness_algorithm_results_dict):
  last_result = master.success_rates[-1]
  last_result_status = 'FLAKE'
  flake_settings = waterfall_config.GetCheckFlakeSettings()
  lower_flake_threshold = flake_settings.get('lower_flake_threshold')
  upper_flake_threshold = flake_settings.get('upper_flake_threshold')

  if (last_result < lower_flake_threshold or
      last_result > upper_flake_threshold):
    last_result_status = 'STABLE'
  if flakiness_algorithm_results_dict['sequential_run_index'] > 0:
    if (last_result_status !=
        flakiness_algorithm_results_dict['lower_boundary_result']):
      master.suspected_flake_build_number = (
          flakiness_algorithm_results_dict['lower_boundary'] +
          flakiness_algorithm_results_dict['sequential_run_index'])
      master.put()
      return 0
  flakiness_algorithm_results_dict['sequential_run_index'] += 1
  return (flakiness_algorithm_results_dict['lower_boundary'] +
          flakiness_algorithm_results_dict['sequential_run_index'])


class NextBuildNumberPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  # Unused argument - pylint: disable=W0613
  def run(self, master_name, builder_name, master_build_number,
          run_build_number, step_name, test_name, test_result_future,
          queue_name, flakiness_algorithm_results_dict):

    # Get MasterFlakeAnalysis success list corresponding to parameters.
    master = MasterFlakeAnalysis.Get(master_name, builder_name,
                                     master_build_number, step_name, test_name)
    # Don't call another pipeline if we fail.
    flake_swarming_task = FlakeSwarmingTask.Get(
        master_name, builder_name, run_build_number, step_name, test_name)

    if flake_swarming_task.status == analysis_status.ERROR:
      master.status = analysis_status.ERROR
      master.put()
      return

    # Figure out what build_number we should call, if any
    if (flakiness_algorithm_results_dict['stabled_out'] and
        flakiness_algorithm_results_dict['flaked_out']):
      next_run = sequential_next_run(master, flakiness_algorithm_results_dict)
    else:
      next_run = get_next_run(master, flakiness_algorithm_results_dict)

    if next_run < flakiness_algorithm_results_dict['last_build_number']:
      next_run = 0
    elif next_run >= master_build_number:
      next_run = 0

    if next_run:
      pipeline_job = RecursiveFlakePipeline(
          master_name, builder_name, next_run, step_name, test_name,
          master_build_number,
          flakiness_algorithm_results_dict=flakiness_algorithm_results_dict)
      # pylint: disable=W0201
      pipeline_job.target = appengine_util.GetTargetNameForModule(
          constants.WATERFALL_BACKEND)
      pipeline_job.start(queue_name=queue_name)
    else:
      master.status = analysis_status.COMPLETED
      master.put()
