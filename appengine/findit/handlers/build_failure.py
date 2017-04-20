# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import copy
from datetime import datetime

from google.appengine.api import users

from common import constants
from common.waterfall import failure_type
from gae_libs.handlers.base_handler import BaseHandler, Permission
from handlers import handlers_util
from handlers import result_status
from handlers.result_status import NO_TRY_JOB_REASON_MAP
from libs import analysis_status
from model import result_status as analysis_result_status
from model import suspected_cl_status
from model.result_status import RESULT_STATUS_TO_DESCRIPTION
from model.suspected_cl_confidence import SuspectedCLConfidence
from model.suspected_cl_status import CL_STATUS_TO_DESCRIPTION
from model.wf_analysis import WfAnalysis
from model.wf_suspected_cl import WfSuspectedCL
from model.wf_try_job import WfTryJob
from waterfall import build_failure_analysis_pipelines
from waterfall import build_util
from waterfall import buildbot
from waterfall import suspected_cl_util
from waterfall import waterfall_config


NON_SWARMING = object()


_ANALYSIS_CL_STATUS_MAP = {
    analysis_result_status.FOUND_CORRECT: suspected_cl_status.CORRECT,
    analysis_result_status.FOUND_INCORRECT: suspected_cl_status.INCORRECT
}


def _FormatDatetime(dt):
  if not dt:
    return None
  else:
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def _GetCLDict(analysis, cl_info):
  if not cl_info:
    return {}

  cl_keys = suspected_cl_util.GetCLInfo(cl_info)
  repo_name = cl_keys[0]
  revision = cl_keys[1]
  for cl in analysis.suspected_cls:
    if cl['repo_name'] == repo_name and cl['revision'] == revision:
      return cl
  return {}


def _GetTriageHistory(analysis):
  if (not users.is_current_user_admin() or
      not analysis.completed or
      not analysis.triage_history):
    return None

  triage_history = []
  for triage_record in analysis.triage_history:
    triage_history.append({
        'triage_time': _FormatDatetime(
            datetime.utcfromtimestamp(triage_record['triage_timestamp'])),
        'user_name': triage_record['user_name'],
        'triaged_cl': _GetCLDict(analysis, triage_record.get('triaged_cl')),
        'result_status': (
            RESULT_STATUS_TO_DESCRIPTION.get(triage_record.get('result_status'))
            or CL_STATUS_TO_DESCRIPTION.get(triage_record.get('cl_status'))),
        'version': triage_record.get('version'),
    })

  return triage_history


def _GetOrganizedAnalysisResultBySuspectedCL(analysis_result):
  """Group tests it they have the same suspected CLs."""
  organized_results = defaultdict(list)

  if not analysis_result:
    return organized_results

  for step_failure in analysis_result.get('failures', []):
    step_name = step_failure['step_name']
    supported = step_failure.get('supported', True)
    step_revisions_index = {}
    organized_suspected_cls = organized_results[step_name]

    if not step_failure.get('tests'):
      # Non swarming, just group the whole step together.
      shared_result = {
          'first_failure': step_failure['first_failure'],
          'last_pass': step_failure.get('last_pass'),
          'supported': supported,
          'tests': [],
          'suspected_cls': step_failure['suspected_cls']
      }
      organized_suspected_cls.append(shared_result)
      continue

    # Swarming tests.
    for index, cl in enumerate(step_failure['suspected_cls']):
      step_revisions_index[cl['revision']] = index

    # Groups tests by suspected CLs' revision.
    # Keys are the indices of each test in the test list.
    # Format is as below:
    # {
    #     1: {
    #         'tests': ['test1', 'test2'],
    #         'revisions': ['rev1'],
    #         'suspected_cls': [
    #             # suspected cl info for rev1 at step level.
    #         ]
    #     },
    #     3: {
    #         'tests': ['test3'],
    #         'revisions': ['rev3', 'rev2'],
    #         'suspected_cls': [
    #             # suspected cl info for rev2, rev3 at step level.
    #         ]
    #     }
    # }
    tests_group = defaultdict(list)
    for index, test in enumerate(step_failure['tests']):
      # Get all revisions for this test and check if there is
      # any other test has the same culprit(represented by revision) set.
      test_name = test['test_name']
      found_group = False
      revisions = set()
      for cl in test['suspected_cls']:
        revisions.add(cl['revision'])
      for group in tests_group.values():
        # Found tests that have the same culprit(represented by revision),
        # add current test to group.
        if revisions == set(group['revisions']):
          group['tests'].append(test_name)
          found_group = True
          break
      if not found_group:
        # First test with that revision set, add a new group.
        group_suspected_cls = []
        for revision in revisions:
          group_suspected_cls.append(
              step_failure['suspected_cls'][step_revisions_index[revision]])
        tests_group[index] = {
            'tests': [test_name],
            'revisions': list(revisions),
            'suspected_cls': group_suspected_cls
        }

    for index, group in tests_group.iteritems():
      # Reorganize heuristic results by culprits.
      test_result = step_failure['tests'][index]
      shared_result = {
          'first_failure': test_result['first_failure'],
          'last_pass': test_result.get('last_pass'),
          'supported': supported,
          'tests': group['tests'],
          'suspected_cls': group['suspected_cls']
      }
      organized_suspected_cls.append(shared_result)

  return organized_results


def _GetAnalysisResultWithTryJobInfo(show_debug_info, organized_results,
                                     master_name, builder_name, build_number):
  """Reorganizes analysis result and try job result by step_name and culprit.

  Returns:
    update_result (dict): A dict of classified results.

    The format for those dicts are as below:
    {
        # A dict of results that contains both
        # heuristic analysis results and try job results.
        'reliable_failures': {
            'step1': {
                'results': [
                    {
                        'try_job':{
                            'ref_name': 'step1',
                            'try_job_key': 'm/b/119',
                            'status': analysis_status.COMPLETED,
                            'try_job_url': 'url/121',
                            'try_job_build_number': 121,
                        },
                        'heuristic_analysis': {
                            'suspected_cls': [
                                {
                                    'build_number': 98,
                                    'repo_name': 'chromium',
                                    'revision': 'r98_1',
                                    'commit_position': None,
                                    'url': None,
                                    'score': 5,
                                    'hints': {
                                        'added f98.cc (and it was in log)': 5,
                                    },
                                }
                            ]
                        }
                        'tests': ['test1', 'test2'],
                        'first_failure': 98,
                        'last_pass': 97,
                        'supported': True
                    }
                ]
            }
        },
        # A dict of result for flaky tests.
        'flaky_failures': {...},
        # A dict of results for all the other conditions,
        # such as non-swarming tests or swarming rerun failed.
        'unclassified_failures': {...}
    }
  """
  updated_results = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

  if not organized_results:
    return updated_results

  try_job_info = handlers_util.GetAllTryJobResults(
      master_name, builder_name, build_number, show_debug_info)

  if not try_job_info:
    return updated_results

  for step_name, try_jobs in try_job_info.iteritems():
    try_jobs = try_jobs['try_jobs']
    step_heuristic_results = organized_results[step_name]
    step_updated_results = updated_results[step_name]['results']

    # Finds out try job result index and heuristic result index for each test.
    test_result_map = defaultdict(lambda: defaultdict(int))

    for index, try_job in enumerate(try_jobs):
      if not try_job.get('tests'):  # Compile or non-swarming.
        test_result_map[NON_SWARMING]['try_job_index'] = index
        continue
      for test_name in try_job['tests']:
        test_result_map[test_name]['try_job_index'] = index

    for index, heuristic_result in enumerate(step_heuristic_results):
      if not heuristic_result.get('tests'):  # Compile or non-swarming.
        test_result_map[NON_SWARMING]['heuristic_index'] = index
        continue
      for test_name in heuristic_result['tests']:
        test_result_map[test_name]['heuristic_index'] = index

    # Group tests based on indices.
    indices_test_map = defaultdict(list)
    for test_name, indices in test_result_map.iteritems():
      indices_test_map[
          (indices['try_job_index'], indices['heuristic_index'])].append(
              test_name)

    for (try_job_index, heuristic_index), tests in indices_test_map.iteritems():
      try_job_result = try_jobs[try_job_index]
      heuristic_result = step_heuristic_results[heuristic_index]

      final_result = {
          'try_job': try_job_result,
          'heuristic_analysis': {
              'suspected_cls': heuristic_result['suspected_cls']
          },
          'tests': tests if tests != [NON_SWARMING] else [],
          'first_failure': heuristic_result['first_failure'],
          'last_pass': heuristic_result['last_pass'],
          'supported': heuristic_result['supported']
      }

      if (('status' not in try_job_result or
           try_job_result['status'] in NO_TRY_JOB_REASON_MAP.values()) or
          try_job_result.get('can_force')):
        # There is no try job info but only heuristic result.
        try_job_result['status'] = try_job_result.get(
            'status', result_status.UNKNOWN)
        step_updated_results['unclassified_failures'].append(final_result)
      elif try_job_result['status'] == result_status.FLAKY:
        step_updated_results['flaky_failures'].append(final_result)
      else:
        step_updated_results['reliable_failures'].append(final_result)

  return updated_results


def _PrepareTryJobDataForCompileFailure(analysis):
  try_job_data = {}
  if not (analysis.failure_result_map and  # pragma: no branch.
          constants.COMPILE_STEP_NAME in analysis.failure_result_map):
    return try_job_data  # pragma: no cover.

  referred_build_keys = build_util.GetBuildInfoFromId(
      analysis.failure_result_map[constants.COMPILE_STEP_NAME])
  try_job = WfTryJob.Get(*referred_build_keys)
  if not try_job or not try_job.compile_results:
    return try_job_data  # pragma: no cover.
  result = try_job.compile_results[-1]

  try_job_data['status'] = analysis_status.STATUS_TO_DESCRIPTION.get(
      try_job.status, 'unknown').lower()
  try_job_data['url'] = result.get('url')
  try_job_data['completed'] = try_job.completed
  try_job_data['failed'] = try_job.failed
  try_job_data['culprit'] = result.get(
      'culprit', {}).get(constants.COMPILE_STEP_NAME)

  return try_job_data


def _PopulateHeuristicDataForCompileFailure(analysis, data):
  if analysis.result:  # pragma: no branch.
    compile_failure = None
    for failure in analysis.result.get('failures', []):
      if failure['step_name'] == constants.COMPILE_STEP_NAME:
        compile_failure = failure
    if compile_failure:  # pragma: no branch.
      data['first_failure'] = compile_failure['first_failure']
      data['last_pass'] = compile_failure['last_pass']
      data['suspected_cls_by_heuristic'] = compile_failure['suspected_cls']


def _GetAllSuspectedCLsAndCheckStatus(
    master_name, builder_name, build_number, analysis):
  build_key = build_util.CreateBuildId(
      master_name, builder_name, build_number)
  suspected_cls = copy.deepcopy(analysis.suspected_cls)
  if not suspected_cls:
    return []

  confidences = SuspectedCLConfidence.Get()

  for cl in suspected_cls:
    cl['status'] = _ANALYSIS_CL_STATUS_MAP.get(analysis.result_status, None)
    cl['confidence'] = None

    suspected_cl = WfSuspectedCL.Get(cl['repo_name'], cl['revision'])
    if not suspected_cl:
      continue

    build = suspected_cl.builds.get(build_key)
    if build:
      cl['status'] = build['status']
      cl['confidence'] = '%d%%' % (
          suspected_cl_util.GetSuspectedCLConfidenceScore(confidences, build))

  return suspected_cls


class BuildFailure(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def _ShowTriageHelpButton(self):
    return users.is_current_user_admin()

  def _PrepareCommonDataForFailure(self, analysis):
    return {
        'master_name': analysis.master_name,
        'builder_name': analysis.builder_name,
        'build_number': analysis.build_number,
        'pipeline_status_path': analysis.pipeline_status_path,
        'show_debug_info': self._ShowDebugInfo(),
        'analysis_request_time': _FormatDatetime(analysis.request_time),
        'analysis_start_time': _FormatDatetime(analysis.start_time),
        'analysis_end_time': _FormatDatetime(analysis.end_time),
        'analysis_duration': analysis.duration,
        'analysis_update_time': _FormatDatetime(analysis.updated_time),
        'analysis_completed': analysis.completed,
        'analysis_failed': analysis.failed,
        'analysis_correct': analysis.correct,
        'analysis_is_duplicate': analysis.is_duplicate,
        'triage_history': _GetTriageHistory(analysis),
        'show_triage_help_button': self._ShowTriageHelpButton(),
        'triage_reference_analysis_master_name':
            analysis.triage_reference_analysis_master_name,
        'triage_reference_analysis_builder_name':
            analysis.triage_reference_analysis_builder_name,
        'triage_reference_analysis_build_number':
            analysis.triage_reference_analysis_build_number
    }

  def _PrepareDataForCompileFailure(self, analysis, data):
    data['infra_exception'] = analysis.failure_type == failure_type.INFRA
    # Check result from heuristic analysis.
    _PopulateHeuristicDataForCompileFailure(analysis, data)
    # Check result from try job.
    data['try_job'] = _PrepareTryJobDataForCompileFailure(analysis)

  def _PrepareDataForTestFailures(self, analysis, build_info, data,
                                  show_debug_info=False):

    data['status_message_map'] = result_status.STATUS_MESSAGE_MAP

    organized_results = _GetOrganizedAnalysisResultBySuspectedCL(
        analysis.result)
    analysis_result = _GetAnalysisResultWithTryJobInfo(
        show_debug_info, organized_results, *build_info)

    data['analysis_result'] = analysis_result
    return data

  def HandleGet(self):
    """Triggers analysis of a build failure on demand and return current result.

    If the final analysis result is available, set cache-control to 1 day to
    avoid overload by unnecessary and frequent query from clients; otherwise
    set cache-control to 5 seconds to allow repeated query.

    Serve HTML page or JSON result as requested.
    """
    url = self.request.get('url').strip()
    build_info = buildbot.ParseBuildUrl(url)
    if not build_info:
      return BaseHandler.CreateError(
          'Url "%s" is not pointing to a build.' % url, 501)
    master_name, builder_name, build_number = build_info

    analysis = None
    if not (waterfall_config.MasterIsSupported(master_name) or
            users.is_current_user_admin()):
      # If the build failure was already analyzed, just show it to the user.
      analysis = WfAnalysis.Get(master_name, builder_name, build_number)
      if not analysis:
        return BaseHandler.CreateError(
            'Master "%s" is not supported yet.' % master_name, 501)

    if not analysis:
      # Only allow admin to force a re-run and set the build_completed.
      force = (users.is_current_user_admin() and
               self.request.get('force') == '1')

      build = build_util.GetBuildInfo(master_name, builder_name, build_number)
      if not build:
        return BaseHandler.CreateError(
            'Can\'t get information about build "%s/%s/%s".' % (
              master_name, builder_name, build_number), 501)
      build_completed = build.completed

      if not build_completed and force:
        return BaseHandler.CreateError(
            'Can\'t rerun an incomplete build "%s/%s/%s".' % (
                master_name, builder_name, build_number), 501)

      analysis = build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
          master_name, builder_name, build_number,
          build_completed=build_completed, force=force,
          queue_name=constants.WATERFALL_ANALYSIS_QUEUE)

    data = self._PrepareCommonDataForFailure(analysis)
    data['suspected_cls'] = _GetAllSuspectedCLsAndCheckStatus(
        master_name, builder_name, build_number, analysis)

    # TODO(crbug.com/702444): Do not assume failure_type.INFRA implies a
    # compile failure. Either use a special template, or choose the appropriate
    # one based on the type of job (compile/test).
    if analysis.failure_type == failure_type.COMPILE or (
        analysis.failure_type == failure_type.INFRA):
      self._PrepareDataForCompileFailure(analysis, data)
      return {
        'template': 'waterfall/compile_failure.html',
        'data': data
      }
    else:
      self._PrepareDataForTestFailures(
        analysis, build_info, data, self._ShowDebugInfo())
      return {
        'template': 'waterfall/test_failure.html',
        'data': data
      }

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
