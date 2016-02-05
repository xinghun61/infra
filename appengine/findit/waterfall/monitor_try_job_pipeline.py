# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import time

from common import buildbucket_client
from common.buildbucket_client import BuildbucketBuild
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from pipeline_wrapper import BasePipeline
from pipeline_wrapper import pipeline
from waterfall.try_job_type import TryJobType


class MonitorTryJobPipeline(BasePipeline):
  """A pipeline for monitoring a try job and recording results when it's done.

  The result will be stored to compile_results or test_results according to
  which type of build failure we are running try job for.
  """

  BUILDBUCKET_CLIENT_QUERY_INTERVAL_SECONDS = 60
  TIMEOUT = 'TIMEOUT'

  @staticmethod
  def _MicrosecondsToDatetime(microseconds):
    """Returns a datetime given the number of microseconds, or None."""
    if microseconds:
      return datetime.fromtimestamp(float(microseconds) / 1000000)
    return None

  @staticmethod
  def _UpdateTryJobMetadataForBuildError(try_job_data, error):
    try_job_data.error = {
        'message': error.message,
        'reason': error.reason
    }
    try_job_data.put()

  @staticmethod
  def _UpdateTryJobMetadataForCompletedBuild(try_job_data, build, start_time,
                                             timed_out=False):
    try_job_data.request_time = MonitorTryJobPipeline._MicrosecondsToDatetime(
        build.request_time)
    # If start_time is unavailable, fallback to request_time.
    try_job_data.start_time = start_time or try_job_data.request_time
    try_job_data.end_time = MonitorTryJobPipeline._MicrosecondsToDatetime(
        build.end_time)
    try_job_data.number_of_commits_analyzed = len(
        build.report.get('result', {}))
    try_job_data.try_job_url = build.url  # pragma: no cover
    try_job_data.regression_range_size = build.report.get(
        'metadata', {}).get('regression_range_size')
    if timed_out:
      try_job_data.error = {
          'message': MonitorTryJobPipeline.TIMEOUT,
          'reason': MonitorTryJobPipeline.TIMEOUT
      }
    try_job_data.put()

  def _UpdateTryJobResult(
      self, status, master_name, builder_name, build_number, try_job_type,
      try_job_id, try_job_url, result_content=None):
    """Updates try job result based on responsed try job status and result."""
    result = {
        'report': result_content,
        'url': try_job_url,
        'try_job_id': try_job_id,
    }

    try_job_result = WfTryJob.Get(master_name, builder_name, build_number)
    if try_job_type == TryJobType.COMPILE:
      result_to_update = try_job_result.compile_results
    else:
      result_to_update = try_job_result.test_results
    if (result_to_update and
        result_to_update[-1]['try_job_id'] == try_job_id):
      result_to_update[-1].update(result)
    else:  # pragma: no cover
      # Normally result for current try job should've been saved in
      # schedule_try_job_pipeline, so this branch shouldn't be reached.
      result_to_update.append(result)

    if status == BuildbucketBuild.STARTED:  # pragma: no cover
      try_job_result.status = wf_analysis_status.ANALYZING
    try_job_result.put()
    return result_to_update

  # Arguments number differs from overridden method - pylint: disable=W0221
  # TODO(chanli): Handle try job for test failures later.
  def run(
      self, master_name, builder_name, build_number, try_job_type, try_job_id):
    assert try_job_id

    timeout_hours = 5
    deadline = time.time() + timeout_hours * 60 * 60
    try_job_data = (WfTryJobData.Get(try_job_id) or
                    WfTryJobData.Create(try_job_id))
    try_job_data.master_name = master_name
    try_job_data.builder_name = builder_name
    try_job_data.try_job_type = try_job_type

    already_set_started = False
    start_time = None
    while True:
      error, build = buildbucket_client.GetTryJobs([try_job_id])[0]
      if error:  # pragma: no cover
        self._UpdateTryJobMetadataForBuildError(try_job_data, error)
        raise pipeline.Retry(
            'Error "%s" occurred. Reason: "%s"' % (error.message, error.reason))
      elif build.status == BuildbucketBuild.COMPLETED:
        self._UpdateTryJobMetadataForCompletedBuild(
            try_job_data, build, start_time)
        result_to_update = self._UpdateTryJobResult(
            BuildbucketBuild.COMPLETED, master_name, builder_name, build_number,
            try_job_type, try_job_id, build.url, build.report)
        return result_to_update[-1]
      else:  # pragma: no cover
        if build.status == BuildbucketBuild.STARTED and not already_set_started:
          # It is possible this branch is skipped if a fast build goes from
          # 'SCHEDULED' to 'COMPLETED' between queries, so start_time may be
          # unavailable.
          start_time = self._MicrosecondsToDatetime(build.updated_time)
          self._UpdateTryJobResult(
              BuildbucketBuild.STARTED, master_name, builder_name, build_number,
              try_job_type, try_job_id, build.url)
          already_set_started = True

        time.sleep(self.BUILDBUCKET_CLIENT_QUERY_INTERVAL_SECONDS)

      if time.time() > deadline:  # pragma: no cover
        try_job_result = WfTryJob.Get(master_name, builder_name, build_number)
        try_job_result.status = wf_analysis_status.ERROR
        try_job_result.put()
        self._UpdateTryJobMetadataForCompletedBuild(
            try_job_data, build, start_time, timed_out=True)
        # Explicitly abort the whole pipeline.
        raise pipeline.Abort(
            'Try job %s timed out after %d hours.' % (
                try_job_id, timeout_hours))
