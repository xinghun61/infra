# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.git_repository import GitRepository
from common.http_client_appengine import HttpClientAppengine as HttpClient
from pipeline_wrapper import pipeline
from pipeline_wrapper import BasePipeline


class PullChangelogPipeline(BasePipeline):
  """A pipeline to pull change log of CLs."""

  # TODO: for files in dependencies(blink, v8, skia, etc), use blame first.
  GIT_REPO = GitRepository(
      'https://chromium.googlesource.com/chromium/src.git', HttpClient())

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, failure_info):
    """
    Args:
      failure_info (dict): Output of pipeline DetectFirstFailurePipeline.run().

    Returns:
      A dict with the following form:
      {
        'git_hash_revision1': common.change_log.ChangeLog.ToDict(),
        ...
      }
    """
    change_logs = {}
    if not failure_info['failed'] or not failure_info['chromium_revision']:
      # Bail out if no failed step or no chromium revision.
      return change_logs

    for build in failure_info.get('builds', {}).values():
      for revision in build['blame_list']:
        change_log = self.GIT_REPO.GetChangeLog(revision)
        if not change_log:  # pragma: no cover
          raise pipeline.Retry('Failed to get change log for %s' % revision)

        change_logs[revision] = change_log.ToDict()

    return change_logs
