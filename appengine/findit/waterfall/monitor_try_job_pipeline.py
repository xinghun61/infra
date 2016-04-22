# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import time

from common.pipeline_wrapper import BasePipeline
from common.pipeline_wrapper import pipeline
from common.waterfall import buildbucket_client
from common.waterfall.buildbucket_client import BuildbucketBuild
from model import analysis_status
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall import waterfall_config
from waterfall.try_job_type import TryJobType


class MonitorTryJobPipeline(BasePipeline):
  """A pipeline for monitoring a try job and recording results when it's done.

  The result will be stored to compile_results or test_results according to
  which type of build failure we are running try job for.
  """

  TIMEOUT = 'TIMEOUT'

  @staticmethod
  def _MicrosecondsToDatetime(microseconds):
    """Returns a datetime given the number of microseconds, or None."""
    if microseconds:
      return datetime.utcfromtimestamp(float(microseconds) / 1000000)
    return None

  @staticmethod
  def _GetError(buildbucket_error, timed_out):
    # TODO(lijeffrey): Currently only timeouts (Findit abandoned monitoring the
    # try job after waiting too long for it to complete) and errors reported
    # directly in the buildbucket_client request are captured. Several other
    # failures can be derrived from the response in the build too which should
    # be determined here.
    if buildbucket_error:
      return {
          'message': buildbucket_error.message,
          'reason': buildbucket_error.reason
      }

    if timed_out:
      return {
          'message': 'Try job monitoring was abandoned.',
          'reason': MonitorTryJobPipeline.TIMEOUT
      }

  @staticmethod
  def _UpdateTryJobMetadata(try_job_data, start_time, buildbucket_build,
                            buildbucket_error, timed_out):
    if buildbucket_build:
      try_job_data.request_time = MonitorTryJobPipeline._MicrosecondsToDatetime(
          buildbucket_build.request_time)
      # If start_time is unavailable, fallback to request_time.
      try_job_data.start_time = start_time or try_job_data.request_time
      try_job_data.end_time = MonitorTryJobPipeline._MicrosecondsToDatetime(
          buildbucket_build.end_time)
      try_job_data.number_of_commits_analyzed = len(
          buildbucket_build.report.get('result', {}))
      try_job_data.try_job_url = buildbucket_build.url
      try_job_data.regression_range_size = buildbucket_build.report.get(
          'metadata', {}).get('regression_range_size')
      try_job_data.last_buildbucket_response = buildbucket_build.response

    error = MonitorTryJobPipeline._GetError(buildbucket_error, timed_out)

    if error:
      try_job_data.error = error

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

    if status == BuildbucketBuild.STARTED:
      try_job_result.status = analysis_status.RUNNING
    try_job_result.put()
    return result_to_update

  # Arguments number differs from overridden method - pylint: disable=W0221
  # TODO(chanli): Handle try job for test failures later.
  def run(
      self, master_name, builder_name, build_number, try_job_type, try_job_id):
    assert try_job_id

    timeout_hours = waterfall_config.GetTryJobSettings().get(
        'job_timeout_hours')
    default_pipeline_wait_seconds = waterfall_config.GetTryJobSettings().get(
        'server_query_interval_seconds')
    max_error_times = waterfall_config.GetTryJobSettings().get(
        'allowed_response_error_times')
    pipeline_wait_seconds = default_pipeline_wait_seconds
    allowed_response_error_times = max_error_times

    # TODO(chanli): Make sure total wait time equals to timeout_hours
    # regardless of retries.
    deadline = time.time() + timeout_hours * 60 * 60
    try_job_data = (WfTryJobData.Get(try_job_id) or
                    WfTryJobData.Create(try_job_id))
    try_job_data.master_name = master_name
    try_job_data.builder_name = builder_name
    try_job_data.build_number = build_number
    try_job_data.try_job_type = try_job_type

    already_set_started = False
    start_time = None
    while True:
      error, build = buildbucket_client.GetTryJobs([try_job_id])[0]
      if error:
        if allowed_response_error_times > 0:
          allowed_response_error_times -= 1
          pipeline_wait_seconds += default_pipeline_wait_seconds
        else:  # pragma: no cover
          # Buildbucket has responded error more than 5 times, retry pipeline.
          self._UpdateTryJobMetadata(
              try_job_data, start_time, build, error, False)
          raise pipeline.Retry(
              'Error "%s" occurred. Reason: "%s"' % (error.message,
                                                     error.reason))
      elif build.status == BuildbucketBuild.COMPLETED:
        self._UpdateTryJobMetadata(
            try_job_data, start_time, build, error, False)
        result_to_update = self._UpdateTryJobResult(
            BuildbucketBuild.COMPLETED, master_name, builder_name, build_number,
            try_job_type, try_job_id, build.url, build.report)
        return result_to_update[-1]
      else:
        if allowed_response_error_times < max_error_times:
          # Recovers from errors.
          allowed_response_error_times = max_error_times
          pipeline_wait_seconds = default_pipeline_wait_seconds
        if build.status == BuildbucketBuild.STARTED and not already_set_started:
          # It is possible this branch is skipped if a fast build goes from
          # 'SCHEDULED' to 'COMPLETED' between queries, so start_time may be
          # unavailable.
          start_time = self._MicrosecondsToDatetime(build.updated_time)
          self._UpdateTryJobResult(
              BuildbucketBuild.STARTED, master_name, builder_name, build_number,
              try_job_type, try_job_id, build.url)
          already_set_started = True

      if time.time() > deadline:  # pragma: no cover
        self._UpdateTryJobMetadata(try_job_data, start_time, build, error, True)
        # Explicitly abort the whole pipeline.
        raise pipeline.Abort(
            'Try job %s timed out after %d hours.' % (
                try_job_id, timeout_hours))

      time.sleep(pipeline_wait_seconds)  # pragma: no cover
