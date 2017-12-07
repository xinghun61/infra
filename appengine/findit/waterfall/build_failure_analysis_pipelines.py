# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common import constants
from common.waterfall import failure_type
from gae_libs import appengine_util
from libs import analysis_status
from libs import time_util
from model.wf_analysis import WfAnalysis
from pipelines.compile_failure.analyze_compile_failure_pipeline import (
    AnalyzeCompileFailurePipeline)
from services import ci_failure
from waterfall.analyze_build_failure_pipeline import AnalyzeBuildFailurePipeline


@ndb.transactional
def NeedANewAnalysis(master_name, builder_name, build_number, failed_steps,
                     build_completed, force):
  """Checks status of analysis for the build and decides if a new one is needed.

  A WfAnalysis entity for the given build will be created if none exists.
  When a new analysis is needed, this function will create and save a WfAnalysis
  entity to the datastore, or it will reset the existing one but still keep the
  result of last analysis.

  Returns:
    True if an analysis is needed, otherwise False.
  """
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)

  if not analysis:
    # The build failure is not analyzed yet.
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = analysis_status.PENDING
    analysis.request_time = time_util.GetUTCNow()
    analysis.put()
    return True
  elif force:
    # A new analysis could be forced if last analysis was completed.
    if not analysis.completed:
      # TODO: start a new analysis if the last one has started running but it
      # has no update for a considerable amount of time, eg. 10 minutes.
      logging.info('Existing analysis is not completed yet. No new analysis.')
      return False

    analysis.Reset()
    analysis.request_time = time_util.GetUTCNow()
    analysis.put()
    return True
  elif failed_steps and analysis.completed:
    # If there is any new failed step, a new analysis is needed.
    for step in failed_steps:
      analyzed = any(step == s for s in analysis.not_passed_steps)
      if analyzed:
        continue

      logging.info('At least one new failed step is detected: %s', step)
      analysis.Reset()
      analysis.request_time = time_util.GetUTCNow()
      analysis.put()
      return True

  # Start a new analysis if the build cycle wasn't completed in last analysis,
  # but now it is completed. This will potentially trigger a try-job run.
  if analysis.completed and not analysis.build_completed and build_completed:
    return True

  # TODO: support following cases
  # * Automatically retry if last analysis failed with errors.
  # * Analysis is not complete and no update in the last 5 minutes.
  logging.info('Not match any cases. No new analysis.')
  return False


def ScheduleAnalysisIfNeeded(master_name,
                             builder_name,
                             build_number,
                             failed_steps=None,
                             build_completed=False,
                             force=False,
                             queue_name=constants.DEFAULT_QUEUE):
  """Schedules an analysis if needed and returns the build analysis.

  When the build failure was already analyzed and a new analysis is scheduled,
  the returned WfAnalysis will still have the result of last completed analysis.

  Args:
    master_name (str): The master name of the failed build.
    builder_name (str): The builder name of the failed build.
    build_number (int): The build number of the failed build.
    failed_steps (list): The names of all failed steps reported for the build.
    build_completed (bool): Indicate whether the build is completed.
    force (bool): If True, a fresh new analysis will be triggered even when an
        old one was completed already; otherwise bail out.
    queue_name (str): The task queue to be used for pipeline tasks.

  Returns:
    A WfAnalysis instance.
  """

  if NeedANewAnalysis(master_name, builder_name, build_number, failed_steps,
                      build_completed, force):
    failure_info, should_proceed = ci_failure.GetBuildFailureInfo(
        master_name, builder_name, build_number)
    if not should_proceed:
      return WfAnalysis.Get(master_name, builder_name, build_number)

    if failure_info['failure_type'] == failure_type.COMPILE:
      # Use new compile pipelines.
      pipeline_job = AnalyzeCompileFailurePipeline(master_name, builder_name,
                                                   build_number, failure_info,
                                                   build_completed, force)
    else:
      pipeline_job = AnalyzeBuildFailurePipeline(master_name, builder_name,
                                                 build_number, failure_info,
                                                 build_completed, force)
    # Explicitly run analysis in the backend module "waterfall-backend".
    # Note: Just setting the target in queue.yaml does NOT work for pipeline
    # when deployed to App Engine, but it does work in dev-server locally.
    # A possible reason is that pipeline will pick a default target if none is
    # specified explicitly, and the default target is used rather than the one
    # in the queue.yaml file, but this contradicts the documentation in
    # https://cloud.google.com/appengine/docs/python/taskqueue/tasks#Task.
    pipeline_job.target = appengine_util.GetTargetNameForModule(
        constants.WATERFALL_BACKEND)
    pipeline_job.start(queue_name=queue_name)

    logging.info('An analysis was scheduled for build %s, %s, %s: %s',
                 master_name, builder_name, build_number,
                 pipeline_job.pipeline_status_path())
  else:
    logging.info('An analysis is not needed for build %s, %s, %s', master_name,
                 builder_name, build_number)

  return WfAnalysis.Get(master_name, builder_name, build_number)
