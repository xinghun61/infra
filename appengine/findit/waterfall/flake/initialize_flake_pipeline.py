# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import appengine_util
from common import constants
from lib import time_util
from model import analysis_status
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import waterfall_config
from waterfall.flake import triggering_sources
from waterfall.flake.recursive_flake_pipeline import RecursiveFlakePipeline


def _NeedANewAnalysis(
    normalized_test, original_test, algorithm_parameters,
    bug_id=None, allow_new_analysis=False, force=False,
    user_email='', triggering_source=triggering_sources.FINDIT_PIPELINE):
  """Checks status of analysis for the test and decides if a new one is needed.

  A MasterFlakeAnalysis entity for the given parameters will be created if none
  exists. When a new analysis is needed, this function will create and
  save a MasterFlakeAnalysis entity to the datastore.

  Args:
    normalized_test (TestInfo): Info of the normalized flaky test after mapping
       a CQ trybot step to a Waterfall buildbot step, striping prefix "PRE_"
       from a gtest, etc.
    original_test (TestInfo): Info of the original flaky test.
    algorithm_parameters (dict): Algorithm parameters to run the analysis.
    bug_id (int): The monorail bug id to update when analysis is done.
    allow_new_analysis (bool): Indicate whether a new analysis is allowed.
    force (bool): Indicate whether to force a rerun of current analysis.
    user_email (str): The user triggering this analysis.
    triggering_source (int): The source from which this analysis was triggered.

  Returns:
    (need_new_analysis, analysis)
    need_new_analysis (bool): True if an analysis is needed, otherwise False.
    analysis (MasterFlakeAnalysis): The MasterFlakeAnalysis entity.
  """
  analysis = MasterFlakeAnalysis.GetVersion(
      normalized_test.master_name, normalized_test.builder_name,
      normalized_test.build_number, normalized_test.step_name,
      normalized_test.test_name)

  def PopulateAnalysisInfo(analysis):
    analysis.Reset()
    analysis.request_time = time_util.GetUTCNow()
    analysis.status = analysis_status.PENDING
    analysis.algorithm_parameters = algorithm_parameters
    analysis.version = appengine_util.GetCurrentVersion()
    analysis.triggering_user_email = user_email
    analysis.triggering_source = triggering_source
    analysis.original_master_name = original_test.master_name
    analysis.original_builder_name = original_test.builder_name
    analysis.original_build_number = original_test.build_number
    analysis.original_step_name = original_test.step_name
    analysis.original_test_name = original_test.test_name
    analysis.bug_id = bug_id

  if not analysis:
    if not allow_new_analysis:
      return False, None
    analysis = MasterFlakeAnalysis.Create(
        normalized_test.master_name, normalized_test.builder_name,
        normalized_test.build_number, normalized_test.step_name,
        normalized_test.test_name)
    PopulateAnalysisInfo(analysis)
    _, saved = analysis.Save()
    return saved, analysis
  elif (analysis.status == analysis_status.PENDING or
        analysis.status == analysis_status.RUNNING):
    return False, analysis
  elif allow_new_analysis and force and analysis.status in (
      analysis_status.ERROR, analysis_status.COMPLETED):
    PopulateAnalysisInfo(analysis)
    _, saved = analysis.Save()
    return saved, analysis
  else:
    return False, analysis


def ScheduleAnalysisIfNeeded(
    normalized_test, original_test, bug_id=None,
    allow_new_analysis=False, force=False, manually_triggered=False,
    user_email=None, triggering_source=triggering_sources.FINDIT_PIPELINE,
    queue_name=constants.DEFAULT_QUEUE):
  """Schedules an analysis if needed and returns the MasterFlakeAnalysis.

  When the build failure was already analyzed and a new analysis is scheduled,
  the returned WfAnalysis will still have the result of last completed analysis.

  Args:
    normalized_test (TestInfo): Info of the normalized flaky test after mapping
       a CQ trybot step to a Waterfall buildbot step, striping prefix "PRE_"
       from a gtest, etc.
    original_test (TestInfo): Info of the original flaky test.
    bug_id (int): The monorail bug id to update when analysis is done.
    allow_new_analysis (bool): Indicate whether a new analysis is allowed.
    force (bool): Indicate whether to force a rerun of current analysis.
    manually_triggered (bool): True if the analysis was requested manually,
      such as by a Chromium sheriff.
    user_email (str): The email of the user requesting the analysis.
    triggering_source (int): From where this analysis was triggered, such as
      through Findit pipeline, UI, or through Findit API.
    queue_name (str): The App Engine queue to run the analysis.

  Returns:
    A MasterFlakeAnalysis instance.
    None if no analysis was scheduled and the user has no permission to.
  """
  algorithm_parameters = waterfall_config.GetCheckFlakeSettings()

  need_new_analysis, analysis = _NeedANewAnalysis(
      normalized_test, original_test, algorithm_parameters, bug_id=bug_id,
      allow_new_analysis=allow_new_analysis, force=force, user_email=user_email,
      triggering_source=triggering_source)

  if need_new_analysis:
    # _NeedANewAnalysis just created master_flake_analysis. Use the latest
    # version number and pass that along to the other pipelines for updating
    # results and data.
    logging.info(
        'A new master flake analysis was successfully saved for %s (%s) and '
        'will be captured in version %s', repr(normalized_test),
        repr(original_test), analysis.version_number)

    max_build_numbers_to_look_back = algorithm_parameters.get(
        'max_build_numbers_to_look_back')
    flakiness_algorithm_results_dict = {
        'flakes_in_a_row': 0,
        'stable_in_a_row': 0,
        'stabled_out': False,
        'flaked_out': False,
        'last_build_number': max(
            0, normalized_test.build_number - max_build_numbers_to_look_back),
        'lower_boundary': None,
        'upper_boundary': None,
        'lower_boundary_result': None,
        'sequential_run_index': 0
    }

    pipeline_job = RecursiveFlakePipeline(
        normalized_test.master_name, normalized_test.builder_name,
        normalized_test.build_number, normalized_test.step_name,
        normalized_test.test_name, analysis.version_number,
        master_build_number=normalized_test.build_number,
        flakiness_algorithm_results_dict=flakiness_algorithm_results_dict,
        manually_triggered=manually_triggered)
    pipeline_job.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    pipeline_job.StartOffPSTPeakHours(queue_name=queue_name)

  return analysis
