# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import logging

from google.appengine.ext import ndb

from common.git_repository import GitRepository
from common.http_client_appengine import HttpClientAppengine as HttpClient
from common.pipeline_wrapper import BasePipeline
from common.waterfall import failure_type
from model import analysis_status
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall.send_notification_for_culprit_pipeline import (
    SendNotificationForCulpritPipeline)


GIT_REPO = GitRepository(
    'https://chromium.googlesource.com/chromium/src.git', HttpClient())


def _GetResultAnalysisStatus(analysis, result):
  """Returns the analysis status based on existing status and try job result.

  Args:
    analysis: The WfAnalysis entity corresponding to this try job.
    result: A result dict containing the result of this try job.

  Returns:
    A result_status code.
  """
  # Only return an updated analysis result status if no results were already
  # found (by the heuristic-based approach) but were by the try job. Note it is
  # possible the heuristic-based result was triaged before the completion of
  # this try job.
  old_result_status = analysis.result_status
  try_job_found_culprit = result and result.get('culprit')

  if (try_job_found_culprit and
      (old_result_status is None or
       old_result_status == result_status.NOT_FOUND_UNTRIAGED or
       old_result_status == result_status.NOT_FOUND_INCORRECT or
       old_result_status == result_status.NOT_FOUND_CORRECT)):
    return result_status.FOUND_UNTRIAGED

  return old_result_status


def _GetSuspectedCLs(analysis, result):
  """Returns a list of suspected CLs.

  Args:
    analysis: The WfAnalysis entity corresponding to this try job.
    result: A result dict containing the culprit from the results of
      this try job.

  Returns:
    A combined list of suspected CLs from those already in analysis and those
    found by this try job.
  """
  suspected_cls = analysis.suspected_cls[:] if analysis.suspected_cls else []
  suspected_cl_revisions = [cl['revision'] for cl in suspected_cls]
  culprit = result.get('culprit')
  compile_cl_info = culprit.get('compile')

  if compile_cl_info:
    # Suspected CL is from compile failure.
    revision = compile_cl_info.get('revision')
    if revision not in suspected_cl_revisions:
      suspected_cl_revisions.append(revision)
      suspected_cls.append(compile_cl_info)
    return suspected_cls

  # Suspected CLs are from test failures.
  for results in culprit.itervalues():
    if results.get('revision'):
      # Non swarming test failures, only have step level failure info.
      revision = results.get('revision')
      cl_info = {
          'url': results.get('url'),
          'repo_name': results.get('repo_name'),
          'revision': results.get('revision'),
          'commit_position': results.get('commit_position')
      }
      if revision not in suspected_cl_revisions:
        suspected_cl_revisions.append(revision)
        suspected_cls.append(cl_info)
    else:
      for test_cl_info in results['tests'].values():
        revision = test_cl_info.get('revision')
        if revision not in suspected_cl_revisions:
          suspected_cl_revisions.append(revision)
          suspected_cls.append(test_cl_info)

  return suspected_cls


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

  if report.get('culprit'):
    return report.get('culprit')

  return _GetFailedRevisionFromResultsDict(report.get('result', {}))


def _GetCulpritsForTestsFromResultsDict(blame_list, test_results):
  culprit_map = {}
  failed_revisions = set()

  for revision in blame_list:
    if not test_results.get(revision):
      continue

    for step, test_result in test_results[revision].iteritems():
      if (not test_result['valid'] or
          test_result['status'] != 'failed'):  # pragma: no cover
        continue

      failed_revisions.add(revision)

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

  return culprit_map, list(failed_revisions)


def _NotifyCulprits(master_name, builder_name, build_number, culprits):
  """Sends notifications to the identified culprits."""
  try:
    for culprit in (culprits or {}).itervalues():
      pipeline = SendNotificationForCulpritPipeline(
          master_name, builder_name, build_number,
          culprit['repo_name'], culprit['revision'])
      pipeline.start()
  except Exception:  # pragma: no cover.
    logging.exception('Failed to notify culprits.')


class IdentifyTryJobCulpritPipeline(BasePipeline):
  """A pipeline to identify culprit CL info based on try job compile results."""

  def _GetCulpritInfo(self, failed_revisions):
    """Gets commit_positions and review urls for revisions."""
    culprits = {}
    # TODO(lijeffrey): remove hard-coded 'chromium' when DEPS file parsing is
    # supported.
    for failed_revision in failed_revisions:
      culprits[failed_revision] = {
          'revision': failed_revision,
          'repo_name': 'chromium'
      }
      change_log = GIT_REPO.GetChangeLog(failed_revision)
      if change_log:
        culprits[failed_revision]['commit_position'] = (
            change_log.commit_position)
        culprits[failed_revision]['url'] = (
            change_log.code_review_url or change_log.commit_url)

    return culprits

  def _FindCulpritForEachTestFailure(self, blame_list, result):
    # For test failures, we need to traverse the result dict in chronological
    # order to identify the culprits for each failed step or test.
    # The earliest revision that a test failed is the culprit.
    culprit_map = defaultdict(dict)
    failed_revisions = set()

    # Recipe should return culprits with the farmat as:
    # 'culprits': {
    #     'step1': {
    #         'test1': 'rev1',
    #         'test2': 'rev2',
    #         ...
    #     },
    #     ...
    # }
    if result['report'].get('culprits'):
      for step_name, tests in result['report']['culprits'].iteritems():
        culprit_map[step_name]['tests'] = {}
        for test_name, revision in tests.iteritems():
          culprit_map[step_name]['tests'][test_name] = {
            'revision': revision
          }
          failed_revisions.add(revision)
      return culprit_map, list(failed_revisions)

    return _GetCulpritsForTestsFromResultsDict(
        blame_list, result['report'].get('result'))

  def _UpdateCulpritMapWithCulpritInfo(self, culprit_map, culprits):
    """Fills in commit_position and review url for each failed rev in map."""
    for step_culprit in culprit_map.values():
      if step_culprit.get('revision'):
        culprit = culprits[step_culprit['revision']]
        step_culprit['commit_position'] = culprit['commit_position']
        step_culprit['url'] = culprit['url']
        step_culprit['repo_name'] = culprit['repo_name']
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
    if try_job_id and result and result.get('report'):
      try_job_data = WfTryJobData.Get(try_job_id)
      if try_job_type == failure_type.COMPILE:
        # For compile failures, the try job will stop if one revision fails, so
        # the culprit will be the last revision in the result.
        failed_revision = _GetFailedRevisionFromCompileResult(result)
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

    @ndb.transactional
    def UpdateTryJobResult():
      try_job_result = WfTryJob.Get(master_name, builder_name, build_number)
      if culprits:
        result_to_update = (
            try_job_result.compile_results if
            try_job_type == failure_type.COMPILE else
            try_job_result.test_results)
        if (result_to_update and
            result_to_update[-1]['try_job_id'] == try_job_id):
          result_to_update[-1].update(result)
        else:  # pragma: no cover
          result_to_update.append(result)
      try_job_result.status = analysis_status.COMPLETED
      try_job_result.put()

    @ndb.transactional
    def UpdateWfAnalysisWithTryJobResult():
      if not culprits:
        return

      # Update analysis result and suspected CLs with results of this try job if
      # culprits were found.
      analysis = WfAnalysis.Get(master_name, builder_name, build_number)
      updated_result_status = _GetResultAnalysisStatus(analysis, result)
      updated_suspected_cls = _GetSuspectedCLs(analysis, result)

      if (analysis.result_status != updated_result_status or
          analysis.suspected_cls != updated_suspected_cls):
        analysis.result_status = updated_result_status
        analysis.suspected_cls = updated_suspected_cls
        analysis.put()

    # Store try-job results.
    UpdateTryJobResult()
    # Add try-job results to WfAnalysis.
    UpdateWfAnalysisWithTryJobResult()

    _NotifyCulprits(master_name, builder_name, build_number, culprits)
    return result.get('culprit') if result else None