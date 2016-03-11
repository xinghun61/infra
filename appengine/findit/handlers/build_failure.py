# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
from datetime import datetime
import os

from google.appengine.api import users

from base_handler import BaseHandler
from base_handler import Permission
from handlers import handlers_util
from model.wf_analysis import WfAnalysis
from model.wf_analysis_result_status import RESULT_STATUS_TO_DESCRIPTION
from waterfall import build_failure_analysis_pipelines
from waterfall import buildbot
from waterfall import waterfall_config


BUILD_FAILURE_ANALYSIS_TASKQUEUE = 'build-failure-analysis-queue'
HEURISTIC = 'heuristic analysis'
TRY_JOB =  'try job'

def _FormatDatetime(dt):
  if not dt:
    return None
  else:
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


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
        'result_status': RESULT_STATUS_TO_DESCRIPTION.get(
            triage_record['result_status']),
        'version': triage_record.get('version'),
    })

  return triage_history


def _UpdateAnalysisResultWithSwarmingTask(result, task_info):
  if not result or not task_info:
    return result

  for failure in result.get('failures', []):
    step_name = failure['step_name']
    if step_name in task_info:
      step_task_info = task_info[step_name]
      if len(step_task_info['swarming_tasks']) > 1:
        failure['swarming_task'] = 'multiple'
      elif len(step_task_info['swarming_tasks']) == 1:
        failure['swarming_task'] = task_info[step_name]['swarming_tasks'][0]
      else:  # pragma: no cover
        continue

      for test in failure.get('tests', []):
        test_name = test['test_name']
        if test_name in step_task_info['tests']:
          test['swarming_task'] = step_task_info['tests'][test_name]


def _GenerateTryJobHint(try_job_url, try_job_build_number):
  if not try_job_url:
    return None
  return 'found by try job <a href="%s"> %d </a>' % (
      try_job_url, try_job_build_number)


def _AddResultSource(result):
  for failure in result.get('failures', []):
    for test in failure.get('tests', []):
      for test_suspected_cl in test['suspected_cls']:
        test_suspected_cl['result_source'] = [HEURISTIC]
    for suspected_cl in failure['suspected_cls']:
      suspected_cl['result_source'] = [HEURISTIC]


def _AddTryJobResultToCulprits(suspected_cls, try_job_info):
  try_job_culprit_revision = try_job_info.get('revision')
  try_job_hint = _GenerateTryJobHint(
      try_job_info.get('try_job_url'),
      try_job_info.get('try_job_build_number'))
  try_job_keys = set()

#  if try_job_culprit_revision:
  for suspected_cl in suspected_cls:
    if suspected_cl.get('try_job_key'):
      try_job_keys.add(suspected_cl.get('try_job_key'))
      continue
    if (try_job_culprit_revision and
        try_job_culprit_revision == suspected_cl.get('revision')):
      # If try job found the same culprit with heuristic based analysis.
      try_job_keys.add(try_job_info['try_job_key'])
      suspected_cl['result_source'] = [HEURISTIC, TRY_JOB]
      suspected_cl['status'] = try_job_info['status']
      suspected_cl['hints'][try_job_hint] = 5
      suspected_cl['score'] += 5
      suspected_cl['try_job_key'] = try_job_info['try_job_key']
      suspected_cl['try_job_url'] = try_job_info.get('try_job_url', '')
      suspected_cl['try_job_build_number'] = (
          try_job_info.get('try_job_build_number'))

  if try_job_info['try_job_key'] not in try_job_keys:
    if try_job_culprit_revision:  # Only found by try job approach.
      try_job_info['result_source'] = [TRY_JOB]
      try_job_info['build_number'] = int(
          try_job_info['try_job_key'].split('/')[-1])
      try_job_info['repo_name'] = 'chromium'
      try_job_info['hints'] = {
          try_job_hint: 5
      }
      try_job_info['score'] = 5
    else: # Try job is not needed or has not finished.
      try_job_info['result_source'] = [TRY_JOB]
    try_job_keys.add(try_job_info['try_job_key'])
    suspected_cls.append(try_job_info)


def _UpdateAnalysisResultWithTryJob(result, try_jobs_info):
  if not result or not try_jobs_info:
    return result

  _AddResultSource(result)
  for failure in result.get('failures', []):
    step_name = failure['step_name']

    if failure.get('tests'):
      for test in failure.get('tests', []):
        test_name = test['test_name']
        step_test_key = '%s-%s' % (step_name, test_name)
        if try_jobs_info.get(step_test_key):
          _AddTryJobResultToCulprits(
              test['suspected_cls'], try_jobs_info[step_test_key])
          # Update step level suspected_cls.
          _AddTryJobResultToCulprits(
              failure['suspected_cls'], try_jobs_info[step_test_key])
    else:
      if try_jobs_info.get(step_name):
        _AddTryJobResultToCulprits(
            failure['suspected_cls'], try_jobs_info[step_name])


def _UpdateAnalysisResult(result, master_name, builder_name, build_number):
  _UpdateAnalysisResultWithSwarmingTask(
      result, handlers_util.GenerateSwarmingTasksData(
          master_name, builder_name, build_number))
  _UpdateAnalysisResultWithTryJob(result, handlers_util.GetAllTryJobResults(
      master_name, builder_name, build_number))


class BuildFailure(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def _ShowDebugInfo(self):
    # Show debug info only if the app is run locally during development, if the
    # currently logged-in user is an admin, or if it is explicitly requested
    # with parameter 'debug=1'.
    return (os.environ['SERVER_SOFTWARE'].startswith('Development') or
            users.is_current_user_admin() or self.request.get('debug') == '1')

  def _ShowTriageHelpButton(self):
    return users.is_current_user_admin()

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

    analysis = None
    master_name = build_info[0]
    if not (waterfall_config.MasterIsSupported(master_name) or
            users.is_current_user_admin()):
      # If the build failure was already analyzed, just show it to the user.
      analysis = WfAnalysis.Get(*build_info)
      if not analysis:
        return BaseHandler.CreateError(
            'Master "%s" is not supported yet.' % master_name, 501)

    if not analysis:
      # Only allow admin to force a re-run and set the build_completed.
      force = (users.is_current_user_admin() and
               self.request.get('force') == '1')
      build_completed = (users.is_current_user_admin() and
                         self.request.get('build_completed') == '1')
      analysis = build_failure_analysis_pipelines.ScheduleAnalysisIfNeeded(
          *build_info, build_completed=build_completed, force=force,
          queue_name=BUILD_FAILURE_ANALYSIS_TASKQUEUE)

    analysis_result = copy.deepcopy(analysis.result)
    _UpdateAnalysisResult(analysis_result, *build_info)

    data = {
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
        'analysis_result': analysis_result,
        'analysis_correct': analysis.correct,
        'triage_history': _GetTriageHistory(analysis),
        'show_triage_help_button': self._ShowTriageHelpButton(),
    }

    return {'template': 'build_failure.html', 'data': data}

  def HandlePost(self):  # pragma: no cover
    return self.HandleGet()
