# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from gae_libs import token
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from gae_libs.http import auth_util
from libs import analysis_status
from libs import time_util
from model import triage_status
from model.flake.analysis import triggering_sources
from model.flake.analysis.flake_analysis_request import FlakeAnalysisRequest
from model.flake.analysis.flake_try_job import FlakeTryJob
from model.flake.analysis.flake_try_job_data import FlakeTryJobData
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from pipelines.flake_failure.analyze_flake_pipeline import AnalyzeFlakePipeline
from waterfall import buildbot
from waterfall.flake import flake_analysis_service


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
          'triage_result': int (correct, incorrect, etc.)
      }
  """
  if not analysis or analysis.suspected_flake_build_number is None:
    return {}

  data_point = analysis.GetDataPointOfSuspectedBuild()

  if not data_point:  # Workaround for analyses by the new pipeline.
    return {
        'build_number': analysis.suspected_flake_build_number,
    }

  return {
      'build_number':
          analysis.suspected_flake_build_number,
      'commit_position':
          data_point.commit_position,
      'git_hash':
          data_point.git_hash,
      'triage_result': (analysis.triage_history[-1].triage_result
                        if analysis.triage_history else triage_status.UNTRIAGED)
  }


def _GetSuspectInfo(suspect_urlsafe_key):
  """Returns a dict with information about a suspect.

  Args:
    suspect_urlsaf_key (str): A urlsafe-key to a FlakeCulprit entity.

  Returns:
    A dict in the format:
      {
          'commit_position': int,
          'git_hash': str,
          'url': str,
      }
  """
  suspect_key = ndb.Key(urlsafe=suspect_urlsafe_key)
  # TODO(crbug.com/799308): Remove this hack when bug is fixed.
  assert suspect_key.pairs()[0]
  assert suspect_key.pairs()[0][0]  # Name of the model.
  assert suspect_key.pairs()[0][1]  # Id of the model.
  suspect = ndb.Key(suspect_key.pairs()[0][0], suspect_key.pairs()[0][1]).get()
  assert suspect

  return {
      'commit_position': suspect.commit_position,
      'git_hash': suspect.revision,
      'url': suspect.url,
  }


def _GetSuspectsInfoForAnalysis(analysis):
  """Returns a list of dicts with information about an analysis' suspected CLs.

  Args:
    analysis (MasterFlakeAnalysis): The master flake analysis the suspected
      flake build is associated with.

  Returns:
    A list of dicts in the format:
        [
            {
                'commit_position': int,
                'git_hash': str,
                'url': str,
            },
            ...
        ]
  """
  if not analysis or not analysis.suspect_urlsafe_keys:
    return []

  suspects_info = []
  for suspect_urlsafe_key in analysis.suspect_urlsafe_keys:
    suspects_info.append(_GetSuspectInfo(suspect_urlsafe_key))
  return suspects_info


def _GetCulpritInfo(analysis):
  """Returns a dict with information about a suspected culprit.

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
  if analysis.culprit_urlsafe_key is None:
    return {}

  suspect_info = _GetSuspectInfo(analysis.culprit_urlsafe_key)
  suspect_info['confidence'] = analysis.confidence_in_culprit
  return suspect_info


def _GetCoordinatesData(analysis):

  def _GetBasicData(point):
    return {
        'commit_position': point.commit_position,
        'pass_rate': point.pass_rate,
        'task_ids': point.task_ids,
        'build_number': point.build_number,
        'git_hash': point.git_hash,
        'try_job_url': point.try_job_url
    }

  if not analysis or not analysis.data_points:
    return []

  # Order by commit position from earliest to latest.
  data_points = sorted(analysis.data_points, key=lambda x: x.commit_position)
  return [_GetBasicData(data_point) for data_point in data_points]


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

  task_id = swarming_task_id if swarming_task_id else None

  return {'task_id': task_id, 'build_number': build_number}


def _GetLastAttemptedTryJobDetails(analysis):
  last_attempted_revision = analysis.last_attempted_revision
  if not last_attempted_revision:
    return {}

  try_job = FlakeTryJob.Get(analysis.master_name, analysis.builder_name,
                            analysis.step_name, analysis.test_name,
                            last_attempted_revision)

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


def _GetDurationForAnalysis(analysis):
  """Returns the duration of the given analysis."""
  if analysis.status == analysis_status.PENDING:
    return None
  return time_util.FormatDuration(analysis.start_time, analysis.end_time or
                                  time_util.GetUTCNow())


def _GetDataPointInfo(data_point):
  """Converts a DataPoint into a form consumable on the template side."""
  data_point_dict = data_point.to_dict()
  commit_position_landed_time = data_point_dict['commit_position_landed_time']
  # Convert commit_position_landed_time from a datetime to string before passing
  # to the template.
  data_point_dict['commit_position_landed_time'] = (
      str(commit_position_landed_time) if commit_position_landed_time else None)

  # Include the age of the commit as a string.
  data_point_dict['committed_days_ago'] = (
      str(time_util.GetUTCNow() - commit_position_landed_time).split('.')[0]
      if commit_position_landed_time else '')

  # Include the best representative swarming task for display purposes.
  data_point_dict['swarm_task'] = data_point.GetSwarmingTaskId()

  return data_point_dict


class CheckFlake(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def _ShowCustomRunOptions(self, analysis):
    # TODO(lijeffrey): Remove checks for admin and debug flag once analyze
    # manual input for a regression range is implemented.
    return (auth_util.IsCurrentUserAdmin() and
            self.request.get('debug') == '1' and
            analysis.status != analysis_status.RUNNING)

  def _ValidateInput(self, step_name, test_name, bug_id):
    """Ensures the input is valid and generates an error otherwise.

    Args:
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

  @staticmethod
  def _CreateAndScheduleFlakeAnalysis(request,
                                      master_name,
                                      builder_name,
                                      build_number,
                                      step_name,
                                      test_name,
                                      bug_id,
                                      rerun=False):
    # pylint: disable=unused-argument
    """Create and schedule a flake analysis.

    Args:
      request (FlakeAnalysisRequest): The requested step to analyze, containing
          all original fields used to create the request, such as the master,
          builder, etc. on which the the flaky test was originally detected.
      master_name (string): The name of the master with which to
          reference the analysis with.
      builder_name (string): The name of the builder with which to
          reference the analysis with.
      build_number (int): The build number with which to reference
          the analysis with.
      step_name (string): The name of the step with which to reference
          the analysis with.
      test_name (string): The name of the test with which to reference
          the analysis with.
      bug_id (int): The bug id.
      rerun (boolean): Is this analysis a rerun.
    Returns:
      (analysis, scheduled) analysis is the new analysis created.
      scheduled is returned from flake analysis service.
    """
    user_email = auth_util.GetUserEmail()
    is_admin = auth_util.IsCurrentUserAdmin()

    scheduled = flake_analysis_service.ScheduleAnalysisForFlake(
        request,
        user_email,
        is_admin,
        triggering_sources.FINDIT_UI,
        rerun=rerun)

    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, build_number, step_name, test_name)

    return analysis, scheduled

  @staticmethod
  def _CanRerunAnalysis(analysis):
    return not (analysis.status == analysis_status.RUNNING or
                analysis.status == analysis_status.PENDING)

  def _HandleRerunAnalysis(self):
    """Rerun an analysis as a response to a user request."""
    # If the key has been specified, we can derive the above information
    # from the analysis itself.
    if not auth_util.IsCurrentUserAdmin():
      return self.CreateError('Only admin is allowed to rerun.', 403)

    key = self.request.get('key')
    if not key:
      return self.CreateError('No key was provided.', 404)

    analysis = ndb.Key(urlsafe=key).get()
    if not analysis:
      return self.CreateError('Analysis of flake is not found.', 404)

    if not self._CanRerunAnalysis(analysis):
      return self.CreateError(
          'Cannot rerun analysis if one is currently running or pending.', 400)

    logging.info(
        'Rerun button pushed, analysis will be reset and triggered.\n'
        'Analysis key: %s', key)

    request = FlakeAnalysisRequest.Create(analysis.original_test_name, False,
                                          analysis.bug_id)
    request.AddBuildStep(
        analysis.original_master_name, analysis.original_builder_name,
        analysis.original_build_number, analysis.original_step_name,
        time_util.GetUTCNow())

    analysis, _ = self._CreateAndScheduleFlakeAnalysis(
        request, analysis.master_name, analysis.builder_name,
        analysis.build_number, analysis.step_name, analysis.test_name,
        analysis.bug_id, True)

    return self.CreateRedirect(
        '/waterfall/flake?redirect=1&key=%s' % analysis.key.urlsafe())

  def _HandleCancelAnalysis(self):
    """Cancel analysis as a response to a user request."""
    if not auth_util.IsCurrentUserAdmin():
      return self.CreateError('Only admin is allowed to cancel.', 403)

    key = self.request.get('key')
    if not key:
      return self.CreateError('No key was provided.', 404)

    analysis = ndb.Key(urlsafe=key).get()
    if not analysis:
      return self.CreateError('Analysis of flake is not found.', 404)

    if analysis.status != analysis_status.RUNNING:
      return self.CreateError('Can\'t cancel an analysis that\'s complete', 400)

    if not analysis.root_pipeline_id:
      return self.CreateError('No root pipeline found for analysis.', 404)
    root_pipeline = AnalyzeFlakePipeline.from_id(analysis.root_pipeline_id)

    if not root_pipeline:
      return self.CreateError('Root pipeline couldn\'t be found.', 404)

    # If we can find the pipeline, cancel it.
    root_pipeline.abort('Pipeline was cancelled manually.')
    error = {
        'error': 'The pipeline was aborted manually.',
        'message': 'The pipeline was aborted manually.'
    }

    analysis.Update(
        status=analysis_status.ERROR,
        error=error,
        end_time=time_util.GetUTCNow())

    return self.CreateRedirect(
        '/waterfall/flake?redirect=1&key=%s' % analysis.key.urlsafe())

  def _HandleAnalyzeRecentCommit(self):  # pragma: no cover.
    # TODO(crbug.com/889638): Implement handler.
    return self.CreateError(
        'Analyzing a recent commit position is not yet implemented', 403)

  @token.VerifyXSRFToken()
  def HandlePost(self):
    # Information needed to execute this endpoint, will be populated
    # by the branches below.
    rerun = self.request.get('rerun', '0').strip() == '1'
    cancel = self.request.get('cancel', '0').strip() == '1'
    analyze_recent_commit = (
        self.request.get('analyze_recent_commit', '0').strip() == '1')
    if rerun:  # Rerun an analysis.
      return self._HandleRerunAnalysis()
    elif cancel:  # Force an analysis to be cancelled.
      return self._HandleCancelAnalysis()
    elif analyze_recent_commit:
      return self._HandleAnalyzeRecentCommit()
    else:  # Regular POST requests to start an analysis.
      # If the key hasn't been specified, then we get the information from
      # other URL parameters.
      build_url = self.request.get('url', '').strip()
      build_info = buildbot.ParseBuildUrl(build_url)
      if not build_info:
        return self.CreateError('Unknown build info!', 400)
      master_name, builder_name, build_number = build_info

      step_name = self.request.get('step_name', '').strip()
      test_name = self.request.get('test_name', '').strip()
      bug_id = self.request.get('bug_id', '').strip()

      error = self._ValidateInput(step_name, test_name, bug_id)
      if error:
        return error

      build_number = int(build_number)
      bug_id = int(bug_id) if bug_id else None

      request = FlakeAnalysisRequest.Create(test_name, False, bug_id)
      request.AddBuildStep(master_name, builder_name, build_number, step_name,
                           time_util.GetUTCNow())
      analysis, scheduled = self._CreateAndScheduleFlakeAnalysis(
          request, master_name, builder_name, build_number, step_name,
          test_name, bug_id, False)

      if not analysis:
        if scheduled is None:
          # User does not have permission to trigger, nor was any previous
          # analysis triggered to view.
          return {
              'template': 'error.html',
              'data': {
                  'error_message': (
                      'No permission to schedule an analysis for flaky test. '
                      'Please log in with your @google.com account first.'),
              },
              'return_code': 403,
          }

        # Check if a previous request has already covered this analysis so use
        # the results from that analysis.
        request = FlakeAnalysisRequest.GetVersion(key=test_name)

        if not (request and request.analyses):
          return {
              'template': 'error.html',
              'data': {
                  'error_message': (
                      'Flake analysis is not supported for "%s/%s". Either '
                      'the test type is not supported or the test is not '
                      'swarmed yet.' % (step_name, test_name)),
              },
              'return_code': 400,
          }

        analysis = request.FindMatchingAnalysisForConfiguration(
            master_name, builder_name)

        if not analysis:
          logging.error('Flake analysis was deleted unexpectedly!')
          return {
              'template': 'error.html',
              'data': {
                  'error_message': 'Flake analysis was deleted unexpectedly!',
              },
              'return_code': 404,
          }

      logging.info('Analysis: %s has a scheduled status of: %r', analysis.key,
                   scheduled)
      return self.CreateRedirect(
          '/waterfall/flake?redirect=1&key=%s' % analysis.key.urlsafe())

  def HandleGet(self):
    key = self.request.get('key')
    if not key:
      return self.CreateError('No key was provided.', 404)

    analysis = ndb.Key(urlsafe=key).get()
    if not analysis:
      return self.CreateError('Analysis of flake is not found.', 404)

    suspected_flake = _GetSuspectedFlakeInfo(analysis)
    culprit = _GetCulpritInfo(analysis)
    build_level_number, revision_level_number = _GetNumbersOfDataPointGroups(
        analysis.data_points)
    regression_range = analysis.GetLatestRegressionRange()
    culprit_confidence = culprit.get('confidence', 0)

    def AsPercentString(val):
      """0-1 as a percent, rounded and returned as a string"""
      return "{0:d}".format(int(round(val * 100.0))) if val else ''

    culprit_confidence = AsPercentString(culprit_confidence)

    status = analysis.status
    if analysis.heuristic_analysis_status == analysis_status.ERROR:
      status = analysis_status.ERROR

    # Just use utc now when request_time is missing, but don't save it.
    if not analysis.request_time:
      analysis.request_time = time_util.GetUTCNow()

    # Just use utc now when end_time is missing, but don't save it.
    if not analysis.end_time:
      analysis.end_time = time_util.GetUTCNow()

    analysis_complete = analysis.status != analysis_status.RUNNING

    data = {
        'key':
            analysis.key.urlsafe(),
        'pass_rates': [],
        'last_attempted_swarming_task':
            _GetLastAttemptedSwarmingTaskDetails(analysis),
        'last_attempted_try_job':
            _GetLastAttemptedTryJobDetails(analysis),
        'version_number':
            analysis.version_number,
        'suspected_flake':
            suspected_flake,
        'suspected_culprits':
            _GetSuspectsInfoForAnalysis(analysis),
        'culprit':
            culprit,
        'request_time':
            time_util.FormatDatetime(analysis.request_time),
        'ended_days_ago':
            str(time_util.GetUTCNow() - analysis.end_time).split('.')[0],
        'duration':
            str(analysis.end_time - analysis.request_time).split('.')[0],
        'last_updated':
            str(time_util.GetUTCNow() - analysis.updated_time).split('.')[0],
        'analysis_complete':
            analysis_complete,
        'build_level_number':
            build_level_number,
        'revision_level_number':
            revision_level_number,
        'error':
            analysis.error_message,
        'show_admin_options':
            self._ShowCustomRunOptions(analysis),
        'show_debug_options':
            self._ShowDebugInfo(),
        'pipeline_status_path':
            analysis.pipeline_status_path,

        # new ui stuff
        'master_name':
            analysis.original_master_name or analysis.master_name,
        'builder_name':
            analysis.original_builder_name or analysis.builder_name,
        'build_number':
            analysis.original_build_number or analysis.build_number,
        'step_name':
            analysis.original_step_name or analysis.step_name,
        'test_name':
            analysis.original_test_name or analysis.test_name,
        'regression_range_upper':
            regression_range.upper,
        'regression_range_lower':
            regression_range.lower,
        'culprit_url':
            culprit.get('url', ''),
        'culprit_revision': (culprit.get('commit_position', 0) or
                             culprit.get('git_hash', '')),
        'culprit_confidence':
            culprit_confidence,
        'bug_id':
            str(analysis.bug_id) if analysis.bug_id else '',
        'status':
            analysis_status.STATUS_TO_DESCRIPTION.get(status).lower(),
    }

    if (auth_util.IsCurrentUserAdmin() and analysis.completed and
        analysis.triage_history):
      data['triage_history'] = analysis.GetTriageHistory()

    data['pending_time'] = time_util.FormatDuration(
        analysis.request_time, analysis.start_time or time_util.GetUTCNow())
    data['duration'] = _GetDurationForAnalysis(analysis)

    data['pass_rates'] = _GetCoordinatesData(analysis)

    # Show the most up-to-date flakiness.
    latest_data_point = analysis.GetLatestDataPoint()
    if latest_data_point:
      recent_flakiness_dict = _GetDataPointInfo(latest_data_point)
      data['most_recent_flakiness'] = recent_flakiness_dict

    return {'template': 'flake/result.html', 'data': data}
