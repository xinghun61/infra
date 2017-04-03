# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import copy

from google.appengine.ext import ndb

from common.waterfall import failure_type
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.pipeline_wrapper import BasePipeline
from model import analysis_approach_type
from model import analysis_status
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from waterfall import suspected_cl_util
from waterfall.revert_and_notify_culprit_pipeline import (
    RevertAndNotifyCulpritPipeline)

GIT_REPO = CachedGitilesRepository(
    HttpClientAppengine(), 'https://chromium.googlesource.com/chromium/src.git')


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


def _GetSuspectedCLs(analysis, try_job_type, result, culprits):
  """Returns a list of suspected CLs.

  Args:
    analysis: The WfAnalysis entity corresponding to this try job.
    try_job_type: Try job type, COMPILE or TEST, the same with failure type.
    result: A result dict containing the result of this try job.
    culprits: A list of suspected CLs found by the try job.

  Returns:
    A combined list of suspected CLs from those already in analysis and those
    found by this try job.
  """
  suspected_cls = analysis.suspected_cls[:] if analysis.suspected_cls else []
  suspected_cl_revisions = [cl['revision'] for cl in suspected_cls]

  for revision, try_job_suspected_cl in culprits.iteritems():
    suspected_cl_copy = copy.deepcopy(try_job_suspected_cl)
    if revision not in suspected_cl_revisions:
      suspected_cl_revisions.append(revision)
      if try_job_type == failure_type.COMPILE:
        failures = {'compile': []}
      else:
        failures = _GetTestFailureCausedByCL(
            result.get('report', {}).get('result', {}).get(revision))
      suspected_cl_copy['failures'] = failures
      suspected_cl_copy['top_score'] = None
      suspected_cls.append(suspected_cl_copy)

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
      for failed_test in test_result['failures']:
        # Swarming tests, gets first failed revision for each test.
        if failed_test not in culprit_map[step]['tests']:
          culprit_map[step]['tests'][failed_test] = {
              'revision': revision
          }

  return culprit_map, list(failed_revisions)


def _GetSuspectedCLFoundByHeuristicForCompile(analysis):
  """For compile failure, gets the suspected revision found by heuristic."""
  if not analysis or not analysis.result:
    return None

  for failure in analysis.result.get('failures', []):
    if (failure['step_name'].lower() == 'compile' and
        len(failure['suspected_cls']) == 1):
      # Based on confidence calculation, suspected_cl found by heuristic for
      # compile is very likely to be the culprit.
      # Since the current confidence calculation is for results with single
      # suspected_cl, we might need to have the same regulation here.
      return failure['suspected_cls'][0]
  return None


def _GetHeuristicSuspectedCLs(analysis):
  """Gets revisions of suspected cls found by heuristic approach."""
  if analysis and analysis.suspected_cls:
    return [[cl['repo_name'], cl['revision']] for cl in analysis.suspected_cls]
  return []


def _GetTestFailureCausedByCL(result):
  if not result:
    return None

  failures = {}
  for step_name, step_result in result.iteritems():
    if step_result['status'] == 'failed':
      failures[step_name] = step_result['failures']

  return failures


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

    # Recipe should return culprits with the format as:
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
      for test_culprit in step_culprit.get('tests', {}).values():
        test_revision = test_culprit['revision']
        test_culprit.update(culprits[test_revision])

  def _GetCulpritDataForTest(self, culprit_map):
    """Gets culprit revision for each failure for try job metadata."""
    culprit_data = {}
    for step, step_culprit in culprit_map.iteritems():
      culprit_data[step] = {}
      for test, test_culprit in step_culprit['tests'].iteritems():
        culprit_data[step][test] = test_culprit['revision']
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
        results_to_update = (
            try_job_result.compile_results if
            try_job_type == failure_type.COMPILE else
            try_job_result.test_results)
        updated = False
        for result_to_update in results_to_update:
          if try_job_id == result_to_update['try_job_id']:  # pragma: no branch
            result_to_update.update(result)
            updated = True
            break

        if not updated:  # pragma: no cover
          results_to_update.append(result)

      try_job_result.status = analysis_status.COMPLETED
      try_job_result.put()

    @ndb.transactional
    def UpdateWfAnalysisWithTryJobResult():
      if not culprits:
        return

      analysis = WfAnalysis.Get(master_name, builder_name, build_number)
      # Update analysis result and suspected CLs with results of this try job if
      # culprits were found.
      updated_result_status = _GetResultAnalysisStatus(analysis, result)
      updated_suspected_cls = _GetSuspectedCLs(
          analysis, try_job_type, result, culprits)
      if (analysis.result_status != updated_result_status or
          analysis.suspected_cls != updated_suspected_cls):
        analysis.result_status = updated_result_status
        analysis.suspected_cls = updated_suspected_cls
        analysis.put()

    def UpdateSuspectedCLs():
      if not culprits:
        return

      # Creates or updates each suspected_cl.
      for culprit in culprits.values():
        revision = culprit['revision']
        if try_job_type == failure_type.COMPILE:
          failures = {'compile': []}
        else:
          failures = _GetTestFailureCausedByCL(
              result.get('report', {}).get('result', {}).get(revision))

        suspected_cl_util.UpdateSuspectedCL(
            culprit['repo_name'], revision, culprit.get('commit_position'),
            analysis_approach_type.TRY_JOB, master_name, builder_name,
            build_number, try_job_type, failures, None)

    # Store try-job results.
    UpdateTryJobResult()

    # Saves cls found by heuristic approach for later use.
    # This part must be before UpdateWfAnalysisWithTryJobResult().
    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    heuristic_cls = _GetHeuristicSuspectedCLs(analysis)
    compile_suspected_cl = (
        _GetSuspectedCLFoundByHeuristicForCompile(analysis)
        if try_job_type == failure_type.COMPILE else None)

    # Add try-job results to WfAnalysis.
    UpdateWfAnalysisWithTryJobResult()

    # TODO (chanli): Update suspected_cl for builds in the same group with
    # current build.
    # Updates suspected_cl.
    UpdateSuspectedCLs()

    yield RevertAndNotifyCulpritPipeline(
        master_name, builder_name, build_number, culprits, heuristic_cls,
        compile_suspected_cl, try_job_type)
