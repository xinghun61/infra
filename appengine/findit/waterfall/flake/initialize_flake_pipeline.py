# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from google.appengine.ext import ndb

from common import appengine_util
from common import constants
from model import analysis_status
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall.flake.recursive_flake_pipeline import RecursiveFlakePipeline

# TODO(lijeffrey): Move to config.
MAX_BUILD_NUMBERS_TO_LOOK_BACK = 1000


@ndb.transactional
def NeedANewAnalysis(
    master_name, builder_name, build_number, step_name, test_name):
  """Checks status of analysis for the test and decides if a new one is needed.

  A MasterFlakeAnalysis entity for the given parameters will be created if none
  exists. When a new analysis is needed, this function will create and
  save a MasterFlakeAnalysis entity to the datastore.

  Returns:
    True if an analysis is needed, otherwise False.
  """
  master_flake_analysis = MasterFlakeAnalysis.Get(
      master_name, builder_name, build_number, step_name, test_name)

  if not master_flake_analysis:
    master_flake_analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    master_flake_analysis.status = analysis_status.PENDING
    master_flake_analysis.put()
    return True
  elif (master_flake_analysis.status == analysis_status.COMPLETED or
        master_flake_analysis.status == analysis_status.PENDING or
        master_flake_analysis.status == analysis_status.RUNNING):
    return False
  else:
    # TODO(caiw): Reset method.
    MasterFlakeAnalysis.Get(
        master_name, builder_name, build_number,
        step_name, test_name).key.delete()
    master_flake_analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    master_flake_analysis.status = analysis_status.PENDING
    master_flake_analysis.put()
    return True


# Unused arguments - pylint: disable=W0612, W0613
def ScheduleAnalysisIfNeeded(master_name, builder_name, build_number, step_name,
                             test_name, force=False,
                             queue_name=constants.DEFAULT_QUEUE):
  """Schedules an analysis if needed and returns the MasterFlakeAnalysis.

  When the build failure was already analyzed and a new analysis is scheduled,
  the returned WfAnalysis will still have the result of last completed analysis.

  Args:
    master_name (str): The master name of the failed test
    builder_name (str): The builder name of the failed test
    build_number (int): The build number of the failed test
    step_name (str): The name of the test suite
    test_name (str): The single test we are checking

  Returns:
    A MasterFlakeAnalysis instance.
  """
  if NeedANewAnalysis(
      master_name, builder_name, build_number, step_name, test_name):
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': max(
            0, build_number - MAX_BUILD_NUMBERS_TO_LOOK_BACK),
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0
    }
    pipeline_job = RecursiveFlakePipeline(
        master_name, builder_name, build_number, step_name, test_name,
        master_build_number=build_number,
        flakiness_algorithm_results_dict=flakiness_algorithm_results_dict)
    pipeline_job.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    pipeline_job.start(queue_name=queue_name)
  return MasterFlakeAnalysis.Get(
      master_name, builder_name, build_number, step_name, test_name)
