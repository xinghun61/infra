# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.api import users
from google.appengine.ext import ndb

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from gae_libs.http import auth_util
from libs import analysis_status
from libs import time_util
from model import triage_status
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.flake.flake_try_job import FlakeTryJob
from model.flake.flake_try_job_data import FlakeTryJobData
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import buildbot
from waterfall.flake import flake_analysis_service
from waterfall.flake import triggering_sources
from waterfall.trigger_base_swarming_task_pipeline import NO_TASK
from waterfall.trigger_base_swarming_task_pipeline import NO_TASK_EXCEPTION


def _GetSuspectedFlakeInfo(analysis):
  """Returns a dict with information about the suspected flake build.

  Args:
    analysis (MasterFlakeAnalysis): The master flake analysis the suspected
      flake build is associated with.

  Returns:
    A dict in the format:
      {
          'confidence': float or None,
          'build_number': int,
          'commit_position': int,
          'git_hash': str,
          'lower_bound_commit_position': int,
          'lower_bound_git_hash': str,
          'triage_result': int (correct, incorrect, etc.)
      }
  """
  if analysis.suspected_flake_build_number is None:
    return {}

  data_point = analysis.GetDataPointOfSuspectedBuild()
  assert data_point

  return {
      'confidence': analysis.confidence_in_suspected_build,
      'build_number': analysis.suspected_flake_build_number,
      'commit_position': data_point.commit_position,
      'git_hash': data_point.git_hash,
      'lower_bound_commit_position': (
          data_point.previous_build_commit_position),
      'lower_bound_git_hash': data_point.previous_build_git_hash,
      'triage_result': (
          analysis.triage_history[-1].triage_result if analysis.triage_history
          else triage_status.UNTRIAGED)
  }


def _GetCulpritInfo(analysis):
  """Returns a dict with information about the culprit git_hash.

  Args:
    analysis (MasterFlakeAnalysis): The master flake analysis the suspected
      flake build is associated with.

  Returns:
    A dict in the format:
      {
          'commit_position': int,
          'git_hash': str,
          'url': str,
      }
  """
  if analysis.culprit is None:
    return {}

  return {
      'commit_position': analysis.culprit.commit_position,
      'git_hash': analysis.culprit.revision,
      'url': analysis.culprit.url,
      'confidence': analysis.culprit.confidence,
  }


def _GetCoordinatesData(analysis):

  def _GetBasicData(point):
    return {
        'commit_position': point.commit_position,
        'pass_rate': point.pass_rate,
        'task_id': point.task_id,
        'build_number': point.build_number,
        'git_hash': point.git_hash,
        'try_job_url': point.try_job_url
    }

  if not analysis or not analysis.data_points:
    return []

  # Order by commit position from earliest to latest.
  data_points = sorted(analysis.data_points, key=lambda x: x.commit_position)
  coordinates = []

  previous_data_point = data_points[0]
  data = _GetBasicData(previous_data_point)
  coordinates.append(data)

  for i in range(1, len(data_points)):
    data_point = data_points[i]
    data = _GetBasicData(data_point)
    data['lower_bound_commit_position'] = previous_data_point.commit_position
    data['lower_bound_git_hash'] = previous_data_point.git_hash
    previous_data_point = data_point
    coordinates.append(data)

  return coordinates


def _GetNumbersOfDataPointGroups(data_points):
  build_level_number = 0
  revision_level_number = 0

  for data_point in data_points:
    if data_point.try_job_url:
      revision_level_number += 1
    else:
      build_level_number += 1

  return build_level_number, revision_level_number


def _GetLastAttemptedSwarmingTaskDetails(analysis):
  swarming_task_id = analysis.last_attempted_swarming_task_id
  build_number = analysis.last_attempted_build_number

  task_id = (swarming_task_id if swarming_task_id and
             swarming_task_id.lower() not in (NO_TASK, NO_TASK_EXCEPTION) else
             None)

  return {
      'task_id': task_id,
      'build_number': build_number
  }


def _GetLastAttemptedTryJobDetails(analysis):
  last_attempted_revision = analysis.last_attempted_revision
  if not last_attempted_revision:
    return {}

  try_job = FlakeTryJob.Get(
      analysis.master_name, analysis.builder_name, analysis.step_name,
      analysis.test_name, last_attempted_revision)

  if not try_job or not try_job.try_job_ids:
    return {}

  try_job_id = try_job.try_job_ids[-1]
  try_job_data = FlakeTryJobData.Get(try_job_id)
  if not try_job_data:
    return {}

  return {
      'status': analysis_status.STATUS_TO_DESCRIPTION.get(try_job.status),
      'url': try_job_data.try_job_url
  }


class CheckFlake(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def _ShowInputUI(self, analysis):
    # TODO(lijeffrey): Remove checks for admin and debug flag once analyze
    # manual input for a regression range is implemented.
    return (users.is_current_user_admin() and
            self.request.get('debug') == '1' and
            analysis.status != analysis_status.RUNNING and
            analysis.try_job_status != analysis_status.RUNNING)


  def _ValidateInput(self, step_name, test_name, bug_id):
    """Ensures the input is valid and generates an error otherwise.

    Args:
      master_name (str): The name of the master the flaky test was found on.
      builder_name (str): The name of the builder the flaky test was found on.
      build_number (str): The build number the flaky test was found on.
      step_name (str): The step the flaky test was found on.
      test_name (str): The name of the flaky test.
      bug_id (str): The bug number associated with the flaky test.

    Returns:
      None if all input fields are valid, or an error dict otherwise.
    """
    if not step_name:
      return self.CreateError('Step name must be specified', 400)

    if not test_name:
      return self.CreateError('Test name must be specified', 400)

    if bug_id and not bug_id.isdigit():
      return self.CreateError('Bug id must be an int', 400)

    return None

  def HandleGet(self):
    key = self.request.get('key')
    if key:
      analysis = ndb.Key(urlsafe=key).get()
      if not analysis:  # pragma: no cover
        return self.CreateError('Analysis of flake is not found', 404)
    else:
      build_url = self.request.get('url', '').strip()
      build_info = buildbot.ParseBuildUrl(build_url)
      if not build_info:  # pragma: no cover
        return self.CreateError('Unknown build info!', 400)
      master_name, builder_name, build_number = build_info

      step_name = self.request.get('step_name', '').strip()
      test_name = self.request.get('test_name', '').strip()
      bug_id = self.request.get('bug_id', '').strip()
      # TODO(lijeffrey): Add support for force flag to trigger a rerun.

      error = self._ValidateInput(step_name, test_name, bug_id)

      if error:  # pragma: no cover
        return error

      build_number = int(build_number)
      bug_id = int(bug_id) if bug_id else None
      user_email = auth_util.GetUserEmail()
      is_admin = auth_util.IsCurrentUserAdmin()

      request = FlakeAnalysisRequest.Create(test_name, False, bug_id)
      request.AddBuildStep(master_name, builder_name, build_number, step_name,
                           time_util.GetUTCNow())
      scheduled = flake_analysis_service.ScheduleAnalysisForFlake(
          request, user_email, is_admin, triggering_sources.FINDIT_UI)

      analysis = MasterFlakeAnalysis.GetVersion(
          master_name, builder_name, build_number, step_name, test_name)

      if not analysis:
        if scheduled is None:
          # User does not have permission to trigger, nor was any previous
          # analysis triggered to view.
          return {
              'template': 'error.html',
              'data': {
                  'error_message':
                      ('You could schedule an analysis for flaky test only '
                       'after you login with @google.com account.'),
              },
              'return_code': 401,
          }

        # Check if a previous request has already covered this analysis so use
        # the results from that analysis.
        request = FlakeAnalysisRequest.GetVersion(key=test_name)

        if not (request and request.analyses):
          return {
              'template': 'error.html',
              'data': {
                  'error_message': (
                      'Flake analysis is not supported for this request. Either'
                      ' the build step may not be supported or the test is not '
                      'swarmed.'),
              },
              'return_code': 400,
          }

        analysis = request.FindMatchingAnalysisForConfiguration(
            master_name, builder_name)

        if not analysis:  # pragma: no cover
          logging.error('Flake analysis was deleted unexpectedly!')
          return {
              'template': 'error.html',
              'data': {
                  'error_message': 'Flake analysis was deleted unexpectedly!',
              },
              'return_code': 400
          }

    suspected_flake = _GetSuspectedFlakeInfo(analysis)
    culprit = _GetCulpritInfo(analysis)
    build_level_number, revision_level_number = _GetNumbersOfDataPointGroups(
        analysis.data_points)

    data = {
        'key': analysis.key.urlsafe(),
        'master_name': analysis.master_name,
        'builder_name': analysis.builder_name,
        'build_number': analysis.build_number,
        'step_name': analysis.step_name,
        'test_name': analysis.test_name,
        'pass_rates': [],
        'analysis_status': analysis.status_description,
        'try_job_status': analysis_status.STATUS_TO_DESCRIPTION.get(
            analysis.try_job_status),
        'last_attempted_swarming_task': _GetLastAttemptedSwarmingTaskDetails(
            analysis),
        'last_attempted_try_job': _GetLastAttemptedTryJobDetails(analysis),
        'version_number': analysis.version_number,
        'suspected_flake': suspected_flake,
        'culprit': culprit,
        'request_time': time_util.FormatDatetime(
            analysis.request_time),
        'build_level_number': build_level_number,
        'revision_level_number': revision_level_number,
        'error': analysis.error_message,
        'iterations_to_rerun': analysis.iterations_to_rerun,
        'show_input_ui': self._ShowInputUI(analysis)
    }

    if (users.is_current_user_admin() and analysis.completed and
        analysis.triage_history):
      data['triage_history'] = analysis.GetTriageHistory()

    data['pending_time'] = time_util.FormatDuration(
        analysis.request_time,
        analysis.start_time or time_util.GetUTCNow())
    if analysis.status != analysis_status.PENDING:
      data['duration'] = time_util.FormatDuration(
          analysis.start_time,
          analysis.end_time or time_util.GetUTCNow())

    data['pass_rates'] = _GetCoordinatesData(analysis)

    return {
        'template': 'flake/result.html',
        'data': data
    }
