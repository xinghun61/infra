# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging

from google.appengine.ext import ndb

from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from waterfall import analyze_build_failure_pipeline

@ndb.transactional
def NeedANewAnalysis(
    master_name, builder_name, build_number, failed_steps, force):
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
    analysis.status = wf_analysis_status.PENDING
    analysis.request_time = datetime.utcnow()
    analysis.put()
    return True
  elif force:
    # A new analysis could be forced if last analysis was completed.
    if not analysis.completed:
      # TODO: start a new analysis if the last one has started running but it
      # has no update for a considerable amount of time, eg. 10 minutes.
      return False

    analysis.Reset()
    analysis.request_time = datetime.utcnow()
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
      analysis.request_time = datetime.utcnow()
      analysis.put()
      return True

    return False
  else:
    # TODO: support following cases
    # 1. Automatically retry if last analysis failed with errors.
    # 2. Start another analysis if the build cycle wasn't completed in last
    #    analysis request.
    # 3. Analysis is not complete and no update in the last 5 minutes.
    return False


def ScheduleAnalysisIfNeeded(master_name, builder_name, build_number,
                             failed_steps=None,
                             force=False,
                             queue_name='default'):
  """Schedules an analysis if needed and returns the build analysis.

  When the build failure was already analyzed and a new analysis is scheduled,
  the returned WfAnalysis will still have the result of last completed analysis.

  Args:
    master_name (str): The master name of the failed build.
    builder_name (str): The builder name of the failed build.
    build_number (int): The build number of the failed build.
    failed_steps (list): The names of all failed steps reported for the build.
    force (bool): If True, a fresh new analysis will be triggered even when an
        old one was completed already; otherwise bail out.
    queue_name (str): The task queue to be used for pipeline tasks.

  Returns:
    A WfAnalysis instance.
  """
  if NeedANewAnalysis(
      master_name, builder_name, build_number, failed_steps, force):
    pipeline_job = analyze_build_failure_pipeline.AnalyzeBuildFailurePipeline(
                       master_name, builder_name, build_number)
    pipeline_job.start(queue_name=queue_name)

    logging.info('An analysis was scheduled for build %s, %s, %s: %s',
                 master_name, builder_name, build_number,
                 pipeline_job.pipeline_status_path())

  return WfAnalysis.Get(master_name, builder_name, build_number)
