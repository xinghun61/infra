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
def NeedANewAnalysis(master_name, builder_name, build_number, force):
  """Checks status of analysis for the build and decides if a new one is needed.

  A WfAnalysis entity for the given build will be created if none exists.

  Returns:
    True if an analysis is needed, otherwise False.
  """
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)

  if not analysis:
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = wf_analysis_status.PENDING
    analysis.request_time = datetime.utcnow()
    analysis.put()
    return True
  elif force:
    if not analysis.completed:
      # TODO: start a new analysis if the last one has started running but it
      # has no update for a considerable amount of time, eg. 10 minutes.
      return False

    analysis.Reset()
    analysis.request_time = datetime.utcnow()
    analysis.put()
    return True
  else:
    # TODO: support following cases
    # 1. Automatically retry if last analysis failed with errors.
    # 2. Start another analysis if the build cycle wasn't completed in last
    #    analysis request.
    # 3. Analysis is not complete and no update in the last 5 minutes.
    return False


def ScheduleAnalysisIfNeeded(master_name, builder_name, build_number, force,
                             queue_name):
  """Schedules an analysis if needed and returns the build analysis.

  Args:
    master_name (str): the master name of the failed build.
    builder_name (str): the builder name of the failed build.
    build_number (int): the build number of the failed build.
    force (bool): if True, a fresh new analysis will be triggered even when an
        old one was completed already; otherwise bail out.
    queue_name (str): the task queue to be used for pipeline tasks.

  Returns:
    A WfAnalysis instance.
  """
  if NeedANewAnalysis(master_name, builder_name, build_number, force):
    pipeline_job = analyze_build_failure_pipeline.AnalyzeBuildFailurePipeline(
                       master_name, builder_name, build_number)
    pipeline_job.start(queue_name=queue_name)

    logging.info('An analysis triggered on build %s, %s, %s: %s',
                 master_name, builder_name, build_number,
                 pipeline_job.pipeline_status_path())
  else:  # pragma: no cover
    logging.info('Analysis was already triggered or the result is recent.')

  return WfAnalysis.Get(master_name, builder_name, build_number)
