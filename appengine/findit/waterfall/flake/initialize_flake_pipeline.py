# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from common import constants
from dto.int_range import IntRange
from dto.step_metadata import StepMetadata
from gae_libs import appengine_util
from libs import analysis_status
from libs import time_util
from libs.list_of_basestring import ListOfBasestring
from model.flake.analysis import triggering_sources
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.analyze_flake_pipeline import AnalyzeFlakeInput
from pipelines.flake_failure.analyze_flake_pipeline import AnalyzeFlakePipeline
from pipelines.flake_failure.next_commit_position_pipeline import (
    NextCommitPositionOutput)
from services import ci_failure
from services import try_job as try_job_service
from waterfall import build_util
from waterfall import waterfall_config


def _NeedANewAnalysis(normalized_test,
                      original_test,
                      flake_settings,
                      bug_id=None,
                      allow_new_analysis=False,
                      force=False,
                      user_email='',
                      triggering_source=triggering_sources.FINDIT_PIPELINE):
  """Checks status of analysis for the test and decides if a new one is needed.

  A MasterFlakeAnalysis entity for the given parameters will be created if none
  exists. When a new analysis is needed, this function will create and
  save a MasterFlakeAnalysis entity to the datastore.

  Args:
    normalized_test (TestInfo): Info of the normalized flaky test after mapping
       a CQ trybot step to a Waterfall buildbot step, striping prefix "PRE_"
       from a gtest, etc.
    original_test (TestInfo): Info of the original flaky test.
    flake_settings (dict): The flake settings run on this analysis.
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
    analysis.algorithm_parameters = flake_settings
    analysis.version = appengine_util.GetCurrentVersion()
    analysis.triggering_user_email = user_email
    analysis.triggering_user_email_obscured = False
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
    logging.info('Couldn\'t find analysis.')
    logging.info('Need a new analysis? %r', saved)
    logging.info('analysis key: %s', analysis.key)
    return saved, analysis
  elif (analysis.status == analysis_status.PENDING or
        analysis.status == analysis_status.RUNNING) and not force:
    logging.info(
        'Analysis was in state: %s, can\'t ' +
        'rerun until state is COMPLETED, or FAILED', analysis.status)
    logging.info('Need a new analysis? %r', False)
    logging.info('analysis key: %s', analysis.key)
    return False, analysis
  elif allow_new_analysis and force:
    PopulateAnalysisInfo(analysis)
    _, saved = analysis.Save()
    logging.info('Force given, populated info.')
    logging.info('Need a new analysis? %r', False)
    logging.info('analysis key: %s', analysis.key)
    return saved, analysis
  else:
    return False, analysis


def ScheduleAnalysisIfNeeded(
    normalized_test,
    original_test,
    bug_id=None,
    allow_new_analysis=False,
    force=False,
    manually_triggered=False,
    user_email=None,
    triggering_source=triggering_sources.FINDIT_PIPELINE,
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
  flake_settings = waterfall_config.GetCheckFlakeSettings()

  need_new_analysis, analysis = _NeedANewAnalysis(
      normalized_test,
      original_test,
      flake_settings,
      bug_id=bug_id,
      allow_new_analysis=allow_new_analysis,
      force=force,
      user_email=user_email,
      triggering_source=triggering_source)

  if need_new_analysis:
    # _NeedANewAnalysis just created master_flake_analysis. Use the latest
    # version number and pass that along to the other pipelines for updating
    # results and data.
    logging.info(
        'A new master flake analysis was successfully saved for %s (%s) and '
        'will be captured in version %s', repr(normalized_test),
        repr(original_test), analysis.version_number)

    step_metadata = ci_failure.GetStepMetadata(
        normalized_test.master_name, normalized_test.builder_name,
        normalized_test.build_number, normalized_test.step_name)

    logging.info('Initializing flake analysis pipeline for key: %s',
                 analysis.key)

    _, starting_build_info = build_util.GetBuildInfo(
        normalized_test.master_name, normalized_test.builder_name,
        normalized_test.build_number)

    _, original_build_info = build_util.GetBuildInfo(original_test.master_name,
                                                     original_test.builder_name,
                                                     original_test.build_number)

    assert starting_build_info, (
        'Failed to get starting build for flake analysis')
    starting_commit_position = starting_build_info.commit_position

    assert starting_commit_position is not None, (
        'Cannot analyze flake without a starting commit position')

    assert original_build_info, 'Failed to get original build info'

    # Get the dimensions of the bot for when try jobs are needed to compile.
    dimensions = try_job_service.GetDimensionsFromBuildInfo(starting_build_info)

    analyze_flake_input = AnalyzeFlakeInput(
        analysis_urlsafe_key=analysis.key.urlsafe(),
        analyze_commit_position_parameters=NextCommitPositionOutput(
            culprit_commit_position=None,
            next_commit_position=starting_commit_position),
        commit_position_range=IntRange(
            lower=None, upper=starting_commit_position),
        dimensions=ListOfBasestring.FromSerializable(dimensions),
        manually_triggered=manually_triggered,
        retries=0,
        rerun=force,
        step_metadata=StepMetadata.FromSerializable(step_metadata))

    pipeline_job = AnalyzeFlakePipeline(analyze_flake_input)

    pipeline_job.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    pipeline_job.start(queue_name=queue_name)
    analysis.pipeline_status_path = pipeline_job.pipeline_status_path
    analysis.root_pipeline_id = pipeline_job.root_pipeline_id
    analysis.build_id = starting_build_info.buildbucket_id
    analysis.original_build_id = original_build_info.buildbucket_id
    analysis.put()
    analysis.LogInfo(
        ('A flake analysis was scheduled using commit-based pipelines with '
         'path {}').format(pipeline_job.pipeline_status_path))
  else:
    logging.info('A flake analysis not necessary for build %s, %s, %s, %s',
                 normalized_test.master_name, normalized_test.builder_name,
                 normalized_test.build_number, normalized_test.step_name)

  return analysis
