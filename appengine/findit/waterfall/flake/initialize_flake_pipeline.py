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


def NeedANewAnalysis(
    master_name, builder_name, build_number, step_name, test_name,
    allow_new_analysis=False):
  """Checks status of analysis for the test and decides if a new one is needed.

  A MasterFlakeAnalysis entity for the given parameters will be created if none
  exists. When a new analysis is needed, this function will create and
  save a MasterFlakeAnalysis entity to the datastore.

  TODO(lijeffrey): add support for a force flag to rerun this analysis.

  Returns:
    True if an analysis is needed, otherwise False.
  """
  master_flake_analysis = MasterFlakeAnalysis.GetVersion(
      master_name, builder_name, build_number, step_name, test_name)

  if not master_flake_analysis:
    if not allow_new_analysis:
      return False
    master_flake_analysis = MasterFlakeAnalysis.Create(
        master_name, builder_name, build_number, step_name, test_name)
    master_flake_analysis.created_time = time_util.GetUTCNow()
    master_flake_analysis.status = analysis_status.PENDING
    _, saved = master_flake_analysis.Save()
    return saved
  elif (master_flake_analysis.status == analysis_status.COMPLETED or
        master_flake_analysis.status == analysis_status.PENDING or
        master_flake_analysis.status == analysis_status.RUNNING):
    return False
  else:
    # The previous analysis had some error, so reset and run as a new version.
    master_flake_analysis.Reset()
    _, saved = master_flake_analysis.Save()
    return saved


# Unused arguments - pylint: disable=W0612, W0613
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

  version_number = None

  if NeedANewAnalysis(
      master_name, builder_name, build_number, step_name, test_name,
      allow_new_analysis):

    # NeedANewAnalysis just created master_flake_analysis. Use the latest
    # version number and pass that along to the other pipelines for updating
    # results and data.
    master_flake_analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)
    version_number = master_flake_analysis.version_number
    logging.info(
        'A new master flake analysis was successfully saved for %s/%s/%s/%s/%s '
        'and will be captured in version %s', master_name, builder_name,
        build_number, step_name, test_name, version_number)

    # TODO(lijeffrey): Allow for reruns with custom parameters if the user is
    # not satisfied with the results. Record the custom parameters here.
    check_flake_settings = waterfall_config.GetCheckFlakeSettings()
    master_flake_analysis.algorithm_parameters = check_flake_settings
    master_flake_analysis.put()

    max_build_numbers_to_look_back = check_flake_settings.get(
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
        version_number, master_build_number=build_number,
        flakiness_algorithm_results_dict=flakiness_algorithm_results_dict,
        manually_triggered=manually_triggered)
    pipeline_job.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    pipeline_job.StartOffPSTPeakHours(queue_name=queue_name)
  return MasterFlakeAnalysis.GetVersion(
      master_name, builder_name, build_number, step_name, test_name,
      version=version_number)
