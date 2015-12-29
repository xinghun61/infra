# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from common.git_repository import GitRepository
from common.http_client_appengine import HttpClientAppengine as HttpClient
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from pipeline_wrapper import BasePipeline


class IdentifyTryJobCulpritPipeline(BasePipeline):
  """A pipeline to identify culprit CL info based on try job compile results."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, try_job_id,
      compile_result):
    culprit = None

    if compile_result and compile_result['result']:
      # For compile failure, try job will stop if one revision fails,
      # so culprit will be the last in the result.
      result_for_last_checked_revision = compile_result['result'][-1]
      failed_revision = (
          result_for_last_checked_revision[0] if
          result_for_last_checked_revision[1].lower() == 'failed' else None)

      if failed_revision:
        git_repo = GitRepository(
            'https://chromium.googlesource.com/chromium/src.git', HttpClient())
        change_log = git_repo.GetChangeLog(failed_revision)
        if change_log:
          culprit = {
              'revision': failed_revision,
              'commit_position': change_log.commit_position,
              'review_url': change_log.code_review_url
          }
          compile_result['culprit'] = culprit

    # Store try job results.
    try_job_result = WfTryJob.Get(master_name, builder_name, build_number)
    if culprit:
      if (try_job_result.compile_results and
          try_job_result.compile_results[-1]['try_job_id'] == try_job_id):
        try_job_result.compile_results[-1].update(compile_result)
      else:  # pragma: no cover
        try_job_result.compile_results.append(compile_result)

    try_job_result.status = wf_analysis_status.ANALYZED
    try_job_result.put()

    return culprit
