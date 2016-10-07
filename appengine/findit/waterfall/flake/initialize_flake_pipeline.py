# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import appengine_util
from common import constants
from common import time_util
from model import analysis_status
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import waterfall_config
from waterfall.flake.recursive_flake_pipeline import RecursiveFlakePipeline


def _NeedANewAnalysis(
    master_name, builder_name, build_number, step_name, test_name,
    algorithm_parameters, allow_new_analysis=False, force=False):
  """Checks status of analysis for the test and decides if a new one is needed.

  A MasterFlakeAnalysis entity for the given parameters will be created if none
  exists. When a new analysis is needed, this function will create and
  save a MasterFlakeAnalysis entity to the datastore.

  Args:
    master_name (str): The master name on Waterfall.
    builder_name (str): The builder name on Waterfall.
    build_number (int): The build number on Waterfall.
    step_name (str): The step in which the flaky test is found.
    test_name (str): The flaky test to be analyzed.
    allow_new_analysis (bool): Indicate whether a new analysis is allowed.
    force (bool): Indicate whether to force a rerun of current analysis.

  Returns:
    (need_new_analysis, analysis)
    need_new_analysis (bool): True if an analysis is needed, otherwise False.
    analysis (MasterFlakeAnalysis): The MasterFlakeAnalysis entity.
  """
  analysis = MasterFlakeAnalysis.GetVersion(
      master_name, builder_name, build_number, step_name, test_name)

  if not analysis:
    if not allow_new_analysis:
      return False, None
    analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    analysis.request_time = time_util.GetUTCNow()
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = algorithm_parameters
    analysis.version = appengine_util.GetCurrentVersion()
    _, saved = analysis.Save()
    return saved, analysis
  elif (analysis.status == analysis_status.PENDING or
        analysis.status == analysis_status.RUNNING):
    return False, analysis
  elif allow_new_analysis and force and analysis.status in (
      analysis_status.ERROR, analysis_status.COMPLETED):
    analysis.Reset()
    analysis.request_time = time_util.GetUTCNow()
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = algorithm_parameters
    analysis.version = appengine_util.GetCurrentVersion()
    _, saved = analysis.Save()
    return saved, analysis
  else:
    return False, analysis


def ScheduleAnalysisIfNeeded(master_name, builder_name, build_number, step_name,
                             test_name, allow_new_analysis=False, force=False,
                             manually_triggered=False,
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
    allow_new_analysis (bool): Indicate whether a new analysis is allowed.
    force (bool): Indicate whether to force a rerun of current analysis.
    manually_triggered (bool): True if the analysis is from manual request, like
        by a Chromium sheriff.
    queue_name (str): The App Engine queue to run the analysis.

  Returns:
    A MasterFlakeAnalysis instance.
    None if no analysis was scheduled and the user has no permission to.
  """
  algorithm_parameters = waterfall_config.GetCheckFlakeSettings()

  need_new_analysis, analysis = _NeedANewAnalysis(
      master_name, builder_name, build_number, step_name, test_name,
      algorithm_parameters, allow_new_analysis, force)

  if need_new_analysis:
    # _NeedANewAnalysis just created master_flake_analysis. Use the latest
    # version number and pass that along to the other pipelines for updating
    # results and data.
    logging.info(
        'A new master flake analysis was successfully saved for %s/%s/%s/%s/%s '
        'and will be captured in version %s', master_name, builder_name,
        build_number, step_name, test_name, analysis.version_number)

    max_build_numbers_to_look_back = algorithm_parameters.get(
        'max_build_numbers_to_look_back')
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': max(
            0, build_number - max_build_numbers_to_look_back),
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0
    }

    pipeline_job = RecursiveFlakePipeline(
        master_name, builder_name, build_number, step_name, test_name,
        analysis.version_number, master_build_number=build_number,
        flakiness_algorithm_results_dict=flakiness_algorithm_results_dict,
        manually_triggered=manually_triggered)
    pipeline_job.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    pipeline_job.StartOffPSTPeakHours(queue_name=queue_name)

  return analysis
