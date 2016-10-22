# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module is to provide Findit service APIs through Cloud Endpoints:

Current APIs include:
1. Analysis of compile/test failures in Chromium waterfalls.
   Analyzes failures and detects suspected CLs.
2. Analysis of flakes on Commit Queue.
"""

import json
import logging
import pickle

import endpoints
from google.appengine.api import taskqueue
from protorpc import messages
from protorpc import remote

from common import appengine_util
from common import auth_util
from common import constants
from common import time_util
from common.waterfall import failure_type
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from waterfall import buildbot
from waterfall import waterfall_config
from waterfall.flake import flake_analysis_service


# This is used by the underlying ProtoRpc when creating names for the ProtoRPC
# messages below. This package name will show up as a prefix to the message
# class names in the discovery doc and client libraries.
package = 'FindIt'


# These subclasses of Message are basically definitions of Protocol RPC
# messages. https://cloud.google.com/appengine/docs/python/tools/protorpc/
class _BuildFailure(messages.Message):
  master_url = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(3, variant=messages.Variant.INT32,
                                       required=True)
  # All failed steps of the build reported by the client.
  failed_steps = messages.StringField(4, repeated=True, required=False)


class _BuildFailureCollection(messages.Message):
  """Represents a request from a client, eg. builder_alerts."""
  builds = messages.MessageField(_BuildFailure, 1, repeated=True)


class _SuspectedCL(messages.Message):
  repo_name = messages.StringField(1, required=True)
  revision = messages.StringField(2, required=True)
  commit_position = messages.IntegerField(3, variant=messages.Variant.INT32)


class _AnalysisApproach(messages.Enum):
  HEURISTIC = 1
  TRY_JOB = 2


class _BuildFailureAnalysisResult(messages.Message):
  master_url = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(3, variant=messages.Variant.INT32,
                                       required=True)
  step_name = messages.StringField(4, required=True)
  is_sub_test = messages.BooleanField(5, variant=messages.Variant.BOOL,
                                      required=True)
  test_name = messages.StringField(6)
  first_known_failed_build_number = messages.IntegerField(
      7, variant=messages.Variant.INT32)
  suspected_cls = messages.MessageField(_SuspectedCL, 8, repeated=True)
  analysis_approach = messages.EnumField(_AnalysisApproach, 9)


class _BuildFailureAnalysisResultCollection(messages.Message):
  """Represents a response to the client, eg. builder_alerts."""
  results = messages.MessageField(_BuildFailureAnalysisResult, 1, repeated=True)


class _BuildStep(messages.Message):
  master_name = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(
      3, variant=messages.Variant.INT32, required=True)
  step_name = messages.StringField(4, required=True)


class _Flake(messages.Message):
  name = messages.StringField(1, required=True)
  is_step = messages.BooleanField(2, required=False, default=False)
  bug_id = messages.IntegerField(
      3, variant=messages.Variant.INT32, required=True)
  build_steps = messages.MessageField(_BuildStep, 4, repeated=True)


class _Build(messages.Message):
  master_name = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(
      3, variant=messages.Variant.INT32, required=True)


class _FlakeAnalysis(messages.Message):
  queued = messages.BooleanField(1, required=True)


def _AsyncProcessFailureAnalysisRequests(builds):
  """Pushes a task on the backend to process requests of failure analysis."""
  target = appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND)
  payload = json.dumps({'builds': builds})
  taskqueue.add(
      url=constants.WATERFALL_PROCESS_FAILURE_ANALYSIS_REQUESTS_URL,
      payload=payload, target=target,
      queue_name=constants.WATERFALL_FAILURE_ANALYSIS_REQUEST_QUEUE)


def _AsyncProcessFlakeReport(flake_analysis_request, user_email, is_admin):
  """Pushes a task on the backend to process the flake report."""
  target = appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND)
  payload = pickle.dumps((flake_analysis_request, user_email, is_admin))
  taskqueue.add(
      url=constants.WATERFALL_PROCESS_FLAKE_ANALYSIS_REQUEST_URL,
      payload=payload, target=target,
      queue_name=constants.WATERFALL_FLAKE_ANALYSIS_REQUEST_QUEUE)


# Create a Cloud Endpoints API.
# https://cloud.google.com/appengine/docs/python/endpoints/create_api
@endpoints.api(name='findit', version='v1', description='FindIt API')
class FindItApi(remote.Service):
  """FindIt API v1."""

  def _GenerateBuildFailureAnalysisResult(
      self, build, suspected_cls_in_result, step_name,
      first_failure, test_name=None,
      analysis_approach=_AnalysisApproach.HEURISTIC):
    suspected_cls = []
    for suspected_cl in suspected_cls_in_result:
      suspected_cls.append(_SuspectedCL(
          repo_name=suspected_cl['repo_name'],
          revision=suspected_cl['revision'],
          commit_position=suspected_cl['commit_position']))

    return _BuildFailureAnalysisResult(
        master_url=build.master_url,
        builder_name=build.builder_name,
        build_number=build.build_number,
        step_name=step_name,
        is_sub_test=test_name is not None,
        test_name=test_name,
        first_known_failed_build_number=first_failure,
        suspected_cls=suspected_cls,
        analysis_approach=analysis_approach)

  def _GetCulpritFromTryJob(
      self, try_job_map, build_failure_type, step_name, test_name=None):
    """Returns the culprit found by try-job for the given step or test."""
    if not try_job_map:
      return None

    if test_name is None:
      try_job_key = try_job_map.get(step_name)
    else:
      try_job_key = try_job_map.get(step_name, {}).get(test_name)

    if not try_job_key:
      return None

    try_job = WfTryJob.Get(*try_job_key.split('/'))
    if not try_job or not try_job.completed or try_job.failed:
      return None

    if build_failure_type == failure_type.COMPILE:
      if not try_job.compile_results:  # pragma: no cover.
        return None
      return try_job.compile_results[-1].get('culprit', {}).get(step_name)

    if not try_job.test_results:  # pragma: no cover.
      return None

    if test_name is None:
      step_info = try_job.test_results[-1].get('culprit', {}).get(step_name)
      if not step_info or step_info.get('tests'):  # pragma: no cover.
        # TODO(chanli): For some steps like checkperms/sizes/etc, the culprit
        # finding try-job might have test-level results.
        return None
      return step_info

    task = WfSwarmingTask.Get(*try_job_key.split('/'), step_name=step_name)
    ref_name = (task.parameters.get('ref_name') if task and task.parameters
                else None)
    return try_job.test_results[-1].get('culprit', {}).get(
        ref_name or step_name, {}).get('tests', {}).get(test_name)

  def _PopulateResult(
      self, results, build, try_job_map, build_failure_type,
      heuristic_result, step_name, test_name=None):
    """Appends an analysis result for the given step or test.

    Try-job results are always given priority over heuristic results.
    """
    # Default to heuristic analysis.
    suspected_cls = heuristic_result['suspected_cls']
    analysis_approach = _AnalysisApproach.HEURISTIC

    # Check analysis result from try-job.
    culprit = self._GetCulpritFromTryJob(
        try_job_map, build_failure_type, step_name, test_name=test_name)
    if culprit:
      suspected_cls = [culprit]
      analysis_approach = _AnalysisApproach.TRY_JOB

    if not suspected_cls:
      return

    results.append(self._GenerateBuildFailureAnalysisResult(
        build, suspected_cls, step_name, heuristic_result['first_failure'],
        test_name=test_name, analysis_approach=analysis_approach))

  def _GenerateResultsForBuild(self, build, heuristic_analysis, results):
    for failure in heuristic_analysis.result['failures']:
      if failure.get('tests'):  # Test-level analysis.
        for test in failure['tests']:
          self._PopulateResult(
              results, build, heuristic_analysis.failure_result_map,
              heuristic_analysis.failure_type, test,
              failure['step_name'], test_name=test['test_name'])
      else:
        self._PopulateResult(
            results, build, heuristic_analysis.failure_result_map,
            heuristic_analysis.failure_type, failure, failure['step_name'])

  @endpoints.method(
      _BuildFailureCollection, _BuildFailureAnalysisResultCollection,
      path='buildfailure', name='buildfailure')
  def AnalyzeBuildFailures(self, request):
    """Returns analysis results for the given build failures in the request.

    Analysis of build failures will be triggered automatically on demand.

    Args:
      request (_BuildFailureCollection): A list of build failures.

    Returns:
      _BuildFailureAnalysisResultCollection
      A list of analysis results for the given build failures.
    """
    results = []
    supported_builds = []

    for build in request.builds:
      master_name = buildbot.GetMasterNameFromUrl(build.master_url)
      if not (master_name and waterfall_config.MasterIsSupported(master_name)):
        logging.info('%s/%s/%s is not supported',
                     build.master_url, build.builder_name, build.build_number)
        continue

      supported_builds.append({
          'master_name': master_name,
          'builder_name': build.builder_name,
          'build_number': build.build_number,
          'failed_steps': build.failed_steps,
      })

      # If the build failure was already analyzed and a new analysis is
      # scheduled to analyze new failed steps, the returned WfAnalysis will
      # still have the result from last completed analysis.
      # If there is no analysis yet, no result is returned.
      heuristic_analysis = WfAnalysis.Get(
          master_name, build.builder_name, build.build_number)
      if not heuristic_analysis:
        continue

      if heuristic_analysis.failed or not heuristic_analysis.result:
        # Bail out if the analysis failed or there is no result yet.
        continue

      self._GenerateResultsForBuild(build, heuristic_analysis, results)

    logging.info('%d build failure(s), while %d are supported',
                 len(request.builds), len(supported_builds))
    try:
      _AsyncProcessFailureAnalysisRequests(supported_builds)
    except Exception:  # pragma: no cover.
      # If we fail to post a task to the task queue, we ignore and wait for next
      # request.
      logging.exception('Failed to add analysis request to task queue: %s',
                        repr(supported_builds))

    return _BuildFailureAnalysisResultCollection(results=results)

  @endpoints.method(_Flake, _FlakeAnalysis, path='flake', name='flake')
  def AnalyzeFlake(self, request):
    """Analyze a flake on Commit Queue. Currently only supports flaky tests."""
    user_email = auth_util.GetUserEmail()
    is_admin = auth_util.IsCurrentUserAdmin()

    if not flake_analysis_service.IsAuthorizedUser(user_email, is_admin):
      raise endpoints.UnauthorizedException(
          'No permission to run a new analysis! User is %s' % user_email)

    def CreateFlakeAnalysisRequest(flake):
      analysis_request = FlakeAnalysisRequest.Create(
          flake.name, flake.is_step, flake.bug_id)
      for step in flake.build_steps:
        analysis_request.AddBuildStep(step.master_name, step.builder_name,
                                      step.build_number, step.step_name,
                                      time_util.GetUTCNow())
      return analysis_request

    flake_analysis_request = CreateFlakeAnalysisRequest(request)
    logging.info('Flake report: %s', flake_analysis_request)

    try:
      _AsyncProcessFlakeReport(flake_analysis_request, user_email, is_admin)
      queued = True
    except Exception:
      # Ignore the report when fail to queue it for async processing.
      queued = False
      logging.exception('Failed to queue flake report for async processing')

    return _FlakeAnalysis(queued=queued)
