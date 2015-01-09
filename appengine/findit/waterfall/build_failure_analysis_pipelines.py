# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging

from google.appengine.ext import ndb

from model.build_analysis import BuildAnalysis
from model.build_analysis_status import BuildAnalysisStatus
from waterfall.base_pipeline import BasePipeline
from waterfall.detect_first_failure_pipeline import DetectFirstFailurePipeline


class BuildFailurePipeline(BasePipeline):

  def __init__(self, master_name, builder_name, build_number):
    super(BuildFailurePipeline, self).__init__(
        master_name, builder_name, build_number)
    self.master_name = master_name
    self.builder_name = builder_name
    self.build_number = build_number

  def finalized(self):
    analysis = BuildAnalysis.GetBuildAnalysis(
        self.master_name, self.builder_name, self.build_number)
    if self.was_aborted:  # pragma: no cover
      analysis.status = BuildAnalysisStatus.ERROR
    else:
      analysis.status = BuildAnalysisStatus.ANALYZED
    analysis.put()

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number):
    analysis = BuildAnalysis.GetBuildAnalysis(
        master_name, builder_name, build_number)
    analysis.pipeline_url = self.pipeline_status_url()
    analysis.status = BuildAnalysisStatus.ANALYZING
    analysis.start_time = datetime.utcnow()
    analysis.put()

    yield DetectFirstFailurePipeline(master_name, builder_name, build_number)


@ndb.transactional
def NeedANewAnalysis(master_name, builder_name, build_number, force):
  """Checks status of analysis for the build and decides if a new one is needed.

  A BuildAnalysis entity for the given build will be created if none exists.

  Returns:
    True if an analysis is needed, otherwise False.
  """
  analysis = BuildAnalysis.GetBuildAnalysis(
      master_name, builder_name, build_number)

  if not analysis:
    analysis = BuildAnalysis.CreateBuildAnalysis(
        master_name, builder_name, build_number)
    analysis.status = BuildAnalysisStatus.PENDING
    analysis.put()
    return True
  elif force:
    # TODO: avoid concurrent analysis.
    analysis.Reset()
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
  """Schedules an analysis if needed and returns the build analysis."""
  if NeedANewAnalysis(master_name, builder_name, build_number, force):
    pipeline_job = BuildFailurePipeline(master_name, builder_name, build_number)
    pipeline_job.start(queue_name=queue_name)

    logging.info('An analysis triggered on build %s, %s, %s: %s',
                 master_name, builder_name, build_number,
                 pipeline_job.pipeline_status_url())
  else:  # pragma: no cover
    logging.info('Analysis was already triggered or the result is recent.')

  return BuildAnalysis.GetBuildAnalysis(master_name, builder_name, build_number)
