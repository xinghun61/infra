# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging

from google.appengine.ext import ndb

from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from waterfall.base_pipeline import BasePipeline
from waterfall.detect_first_failure_pipeline import DetectFirstFailurePipeline
from waterfall.extract_signal_pipeline import ExtractSignalPipeline
from waterfall.identify_culprit_pipeline import IdentifyCulpritPipeline
from waterfall.pull_changelog_pipeline import PullChangelogPipeline


class BuildFailurePipeline(BasePipeline):

  def __init__(self, master_name, builder_name, build_number):
    super(BuildFailurePipeline, self).__init__(
        master_name, builder_name, build_number)
    self.master_name = master_name
    self.builder_name = builder_name
    self.build_number = build_number

  def finalized(self):
    # When this root pipeline or its sub-pipelines still run into any error
    # after auto-retries, this root pipeline will be aborted. So, mark the
    # analysis as ERROR. The analysis is created before the pipeline starts.
    if self.was_aborted:  # pragma: no cover
      analysis = WfAnalysis.Get(
          self.master_name, self.builder_name, self.build_number)
      if analysis:  # In case the analysis is deleted manually.
        analysis.status = wf_analysis_status.ERROR
        analysis.put()

  def pipeline_status_path(self):  # pragma: no cover
    """Returns an absolute path to look up the status of the pipeline."""
    return '/_ah/pipeline/status?root=%s&auto=false' % self.root_pipeline_id

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    analysis.pipeline_status_path = self.pipeline_status_path()
    analysis.status = wf_analysis_status.ANALYZING
    analysis.start_time = datetime.utcnow()
    analysis.put()

    # The yield statements below return PipelineFutures, which allow subsequent
    # pipelines to refer to previous output values.
    # https://github.com/GoogleCloudPlatform/appengine-pipelines/wiki/Python
    failure_info = yield DetectFirstFailurePipeline(
        master_name, builder_name, build_number)
    change_logs = yield PullChangelogPipeline(failure_info)
    signals = yield ExtractSignalPipeline(failure_info)
    yield IdentifyCulpritPipeline(failure_info, change_logs, signals)


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
    # TODO: avoid concurrent analysis.
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
    pipeline_job = BuildFailurePipeline(master_name, builder_name, build_number)
    pipeline_job.start(queue_name=queue_name)

    logging.info('An analysis triggered on build %s, %s, %s: %s',
                 master_name, builder_name, build_number,
                 pipeline_job.pipeline_status_url())
  else:  # pragma: no cover
    logging.info('Analysis was already triggered or the result is recent.')

  return WfAnalysis.Get(master_name, builder_name, build_number)
