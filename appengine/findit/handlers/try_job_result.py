# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from base_handler import BaseHandler
from base_handler import Permission
from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from waterfall import buildbot


def _GetTryJobResult(master_name, builder_name, build_number):
  # Get the latest try job result if it's compile failure.
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis:
    return {}

  failure_result_map = analysis.failure_result_map

  if failure_result_map and failure_result_map.get('compile'):
    try_job_key = failure_result_map['compile']
    point_build_keys = try_job_key.split('/')
    try_job = WfTryJob.Get(
          point_build_keys[0], point_build_keys[1], point_build_keys[2])
    if try_job:
      try_job_result = {}
      try_job_result['status'] = (
          wf_analysis_status.STATUS_TO_DESCRIPTION[try_job.status])
      if try_job.compile_results:
        if try_job.compile_results[-1].get('culprit'):
          culprit = try_job.compile_results[-1]['culprit']
          try_job_result['revision'] = culprit['revision']
          try_job_result['commit_position'] = culprit['commit_position']
          try_job_result['review_url'] = culprit['review_url']
        if try_job.compile_results[-1].get('url'):
          try_job_result['try_job_url'] = try_job.compile_results[-1]['url']
      return try_job_result

  return {}


class TryJobResult(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    """Get the latest try job result if it's compile failure."""
    url = self.request.get('url').strip()
    build_keys = buildbot.ParseBuildUrl(url)

    if not build_keys:  # pragma: no cover
      return {'data': {}}

    data = _GetTryJobResult(*build_keys)

    return {'data': data}

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
