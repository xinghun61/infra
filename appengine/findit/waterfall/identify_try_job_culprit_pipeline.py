# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common.git_repository import GitRepository
from common.http_client_appengine import HttpClientAppengine as HttpClient
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from pipeline_wrapper import BasePipeline
from waterfall.try_job_type import TryJobType


GIT_REPO = GitRepository(
    'https://chromium.googlesource.com/chromium/src.git', HttpClient())


class IdentifyTryJobCulpritPipeline(BasePipeline):
  """A pipeline to identify culprit CL info based on try job compile results."""

  def _GetCulpritInfo(self, failed_revisions):
    """Gets commit_positions and review_urls for revisions."""
    culprits = {}
    for failed_revision in failed_revisions:
      culprits[failed_revision] = {
          'revision': failed_revision
      }
      change_log = GIT_REPO.GetChangeLog(failed_revision)
      if change_log:
        culprits[failed_revision]['commit_position'] = (
            change_log.commit_position)
        culprits[failed_revision]['review_url'] = change_log.code_review_url

    return culprits

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
      compile_result: A dict containing the results from a compile. Please refer
      to try_job_result_format.md for format check.

    Returns:
      The failed revision from compile_results, or None if not found.
    """
    if not compile_result:
      return None

    report = compile_result.get('report')

    if not report:
      return None

    return IdentifyTryJobCulpritPipeline._GetFailedRevisionFromResultsDict(
        report.get('result', {}))

  def _FindCulpritForEachTestFailure(self, blame_list, result):
    # For test failures, the try job will run against every revision,
    # so we need to traverse the result dict in chronological order to identify
    # the culprits for each failed step or test.
    culprit_map = {}
    failed_revisions = []
    for revision in blame_list:
      test_results = result['report'].get('result')

      for step, test_result in test_results[revision].iteritems():
        if (not test_result['valid'] or
            test_result['status'] != 'failed'):  # pragma: no cover
          continue

        if revision not in failed_revisions:
          failed_revisions.append(revision)

        if step not in culprit_map:
          culprit_map[step] = {
              'tests': {}
          }

        if (not test_result['failures'] and
            not culprit_map[step].get('revision')):
          # Non swarming test failures, only have step level failure info.
          culprit_map[step]['revision'] = revision

        for failed_test in test_result['failures']:
          # Swarming tests, gets first failed revision for each test.
          if failed_test not in culprit_map[step]['tests']:
            culprit_map[step]['tests'][failed_test] = {
                'revision': revision
            }

    return culprit_map, failed_revisions

  def _UpdateCulpritMapWithCulpritInfo(self, culprit_map, culprits):
    """Fills in commit_position and review_url for each failed rev in map."""
    for step_culprit in culprit_map.values():
      if step_culprit.get('revision'):
        culprit = culprits[step_culprit['revision']]
        step_culprit['commit_position'] = culprit['commit_position']
        step_culprit['review_url'] = culprit['review_url']
      for test_culprit in step_culprit.get('tests', {}).values():
        test_revision = test_culprit['revision']
        test_culprit.update(culprits[test_revision])

  def _GetCulpritDataForTest(self, culprit_map):
    """Gets culprit revision for each failure for try job metadata."""
    culprit_data = {}
    for step, step_culprit in culprit_map.iteritems():
      if step_culprit['tests']:
        culprit_data[step] = {}
        for test, test_culprit in step_culprit['tests'].iteritems():
          culprit_data[step][test] = test_culprit['revision']
      else:
        culprit_data[step] = step_culprit['revision']
    return culprit_data

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, blame_list, try_job_type,
      try_job_id, result):
    """Identifies the information for failed revisions.

    Please refer to try_job_result_format.md for format check.
    """
    culprits = None
    if result and result.get('report'):
      try_job_data = WfTryJobData.Get(try_job_id)
      if try_job_type == TryJobType.COMPILE:
        # For compile failures, the try job will stop if one revision fails, so
        # the culprit will be the last revision in the result.
        failed_revision = self._GetFailedRevisionFromCompileResult(
            result)
        failed_revisions = [failed_revision] if failed_revision else []
        culprits = self._GetCulpritInfo(failed_revisions)
        if culprits:
          result['culprit'] = {
              'compile': culprits[failed_revision]
          }
          try_job_data.culprits = {'compile': failed_revision}
      else:  # try_job_type is 'test'.
        culprit_map, failed_revisions = self._FindCulpritForEachTestFailure(
            blame_list, result)
        culprits = self._GetCulpritInfo(failed_revisions)
        if culprits:
          self._UpdateCulpritMapWithCulpritInfo(culprit_map, culprits)
          result['culprit'] = culprit_map
          try_job_data.culprits = self._GetCulpritDataForTest(culprit_map)
      try_job_data.put()

    # Store try job results.
    try_job_result = WfTryJob.Get(master_name, builder_name, build_number)
    if culprits:
      result_to_update = (
          try_job_result.compile_results if
          try_job_type == TryJobType.COMPILE else
          try_job_result.test_results)
      if (result_to_update and
          result_to_update[-1]['try_job_id'] == try_job_id):
        result_to_update[-1].update(result)
      else:  # pragma: no cover
        result_to_update.append(result)

    try_job_result.status = wf_analysis_status.ANALYZED
    try_job_result.put()

    return result.get('culprit') if result else None
