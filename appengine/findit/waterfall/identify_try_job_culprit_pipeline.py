# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.git_repository import GitRepository
from common.http_client_appengine import HttpClientAppengine as HttpClient
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from pipeline_wrapper import BasePipeline


class IdentifyTryJobCulpritPipeline(BasePipeline):
  """A pipeline to identify culprit CL info based on try job compile results."""

  @staticmethod
  def _GetFailedRevisionFromResultsDict(results_dict):
    """Finds the failed revision from the given dict of revisions.

    Args:
      results_dict: (dict) A dict that maps revisions to their results. For
      example:

      {
          'rev1': 'passed',
          'rev2': 'passed',
          'rev3': 'failed',
      }

      Note results_dict is expected only to have one failed revision which
      will be the one to be returned.

    Returns:
      The revision corresponding to a failed result, if any.
    """
    for revision, result in results_dict.iteritems():
      if result.lower() == 'failed':
        return revision
    return None

  @staticmethod
  def _GetFailedRevisionFromCompileResult(compile_result):
    """Determines the failed revision given compile_result.

    Args:
      compile_result: A dict containing the results from a compile. Curently two
        formats are supported.

        The old format:
        {
            'report': [
                ['rev1', 'passed'],
                ['rev2', 'failed']
            ],
            'url': try job url,
            'try_job_id': try job id
        }

        The new format:
        {
            'report': {
                'result': {
                    'rev1': 'passed',
                    'rev2': 'failed',
                },
                ... (other metadata from the compile result)
            },
            'url': try job url,
            'try_job_id': try job id
        }

    Returns:
      The failed revision from compile_results, or None if not found.
    """
    if not compile_result:
      return None

    report = compile_result.get('report')

    if not report:
      return None

    failed_revision = None

    if isinstance(report, list):
      # TODO(lijeffrey): The format for the result of the compile will change
      # from a list to a dict. This branch is for backwards compatibility and
      # should be removed once result is returned as a dict from the compile
      # recipe. The test recipe may need to be considered as well.

      # For compile failures, the try job will stop if one revision fails, so
      # the culprit will be the last revision in the result.
      result_for_last_checked_revision = report[-1]
      failed_revision = (
          result_for_last_checked_revision[0] if
          result_for_last_checked_revision[1].lower() == 'failed' else None)
    else:
      revision_results = report.get('result', {})
      failed_revision = (
          IdentifyTryJobCulpritPipeline._GetFailedRevisionFromResultsDict(
              revision_results))

    return failed_revision

  @staticmethod
  def _GetCulpritFromFailedRevision(failed_revision):
    """Returns a culprit (dict) using failed_revision, or None."""
    if not failed_revision:
      return None

    git_repo = GitRepository(
        'https://chromium.googlesource.com/chromium/src.git', HttpClient())
    change_log = git_repo.GetChangeLog(failed_revision)

    if not change_log:
      return None

    return {
        'revision': failed_revision,
        'commit_position': change_log.commit_position,
        'review_url': change_log.code_review_url
    }

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, try_job_id,
          compile_result):
    culprit = None
    failed_revision = self._GetFailedRevisionFromCompileResult(compile_result)
    culprit = self._GetCulpritFromFailedRevision(failed_revision)

    # Store try job results.
    try_job_result = WfTryJob.Get(master_name, builder_name, build_number)
    if culprit:
      compile_result['culprit'] = culprit
      if (try_job_result.compile_results and
          try_job_result.compile_results[-1]['try_job_id'] == try_job_id):
        try_job_result.compile_results[-1].update(compile_result)
      else:  # pragma: no cover
        try_job_result.compile_results.append(compile_result)

    try_job_result.status = wf_analysis_status.ANALYZED
    try_job_result.put()

    return culprit
