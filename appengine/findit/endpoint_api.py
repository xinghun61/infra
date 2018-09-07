# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is to provide Findit service APIs through Cloud Endpoints:

Current APIs include:
1. Analysis of compile/test failures in Chromium waterfalls.
   Analyzes failures and detects suspected CLs.
2. Analysis of flakes on Commit Queue.
"""

from collections import defaultdict
from datetime import timedelta
import json
import logging
import pickle

import endpoints
from google.appengine.api import taskqueue
from protorpc import messages
from protorpc import remote

import gae_ts_mon

from common import acl
from common import constants
from common import exceptions
from common.waterfall import failure_type
from gae_libs import appengine_util
from gae_libs.caches import PickledMemCache
from gae_libs.http import auth_util
from libs import analysis_status
from libs import time_util
from libs.cache_decorator import Cached
from model import analysis_approach_type
from model.base_build_model import BaseBuildModel
from model.flake.analysis import triggering_sources
from model.flake.analysis.flake_analysis_request import BuildStep
from model.flake.analysis.flake_analysis_request import FlakeAnalysisRequest
from model.flake.analysis.flake_swarming_task import FlakeSwarmingTask
from model.suspected_cl_confidence import SuspectedCLConfidence
from model.wf_analysis import WfAnalysis
from model.wf_suspected_cl import WfSuspectedCL
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from services.apis import AsyncProcessFlakeReport
from waterfall import buildbot
from waterfall import suspected_cl_util
from waterfall import waterfall_config
from waterfall.flake import step_mapper

# This is used by the underlying ProtoRpc when creating names for the ProtoRPC
# messages below. This package name will show up as a prefix to the message
# class names in the discovery doc and client libraries.
package = 'FindIt'

# How many seconds to cache requests for repeat analyses.
ANALYSIS_CACHE_TIME = 5 * 60


# These subclasses of Message are basically definitions of Protocol RPC
# messages. https://cloud.google.com/appengine/docs/python/tools/protorpc/
class _BuildFailure(messages.Message):
  master_url = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(
      3, variant=messages.Variant.INT32, required=True)
  # All failed steps of the build reported by the client.
  failed_steps = messages.StringField(4, repeated=True, required=False)


class _BuildFailureCollection(messages.Message):
  """Represents a request from a client, eg. builder_alerts."""
  builds = messages.MessageField(_BuildFailure, 1, repeated=True)


class _AnalysisApproach(messages.Enum):
  HEURISTIC = analysis_approach_type.HEURISTIC
  TRY_JOB = analysis_approach_type.TRY_JOB


class _SuspectedCL(messages.Message):
  repo_name = messages.StringField(1, required=True)
  revision = messages.StringField(2, required=True)
  commit_position = messages.IntegerField(3, variant=messages.Variant.INT32)
  confidence = messages.IntegerField(4, variant=messages.Variant.INT32)
  analysis_approach = messages.EnumField(_AnalysisApproach, 5)
  revert_cl_url = messages.StringField(6)
  revert_committed = messages.BooleanField(7, default=False)


class _TryJobStatus(messages.Enum):
  # Try job is pending or running. Can expect result from try job.
  RUNNING = 1
  # There is no try job, try job completed or try job finished with error.
  # Result from try job is ready or no need to continue waiting for it.
  FINISHED = 2


class _BuildFailureAnalysisResult(messages.Message):
  master_url = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(
      3, variant=messages.Variant.INT32, required=True)
  step_name = messages.StringField(4, required=True)
  is_sub_test = messages.BooleanField(
      5, variant=messages.Variant.BOOL, required=True)
  test_name = messages.StringField(6)
  first_known_failed_build_number = messages.IntegerField(
      7, variant=messages.Variant.INT32)
  suspected_cls = messages.MessageField(_SuspectedCL, 8, repeated=True)
  analysis_approach = messages.EnumField(_AnalysisApproach, 9)
  try_job_status = messages.EnumField(_TryJobStatus, 10)
  is_flaky_test = messages.BooleanField(11, variant=messages.Variant.BOOL)
  # Indicates if Findit has any kind of findings: found the culprit or
  # confirmed the test is flaky.
  has_findings = messages.BooleanField(12, variant=messages.Variant.BOOL)
  # If analysis is finished.
  is_finished = messages.BooleanField(13, variant=messages.Variant.BOOL)
  # If the failure is supported.
  is_supported = messages.BooleanField(14, variant=messages.Variant.BOOL)


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
      3, variant=messages.Variant.INT32, required=False)
  build_steps = messages.MessageField(_BuildStep, 4, repeated=True)


class _Build(messages.Message):
  master_name = messages.StringField(1, required=True)
  builder_name = messages.StringField(2, required=True)
  build_number = messages.IntegerField(
      3, variant=messages.Variant.INT32, required=True)


class _FlakeAnalysis(messages.Message):
  queued = messages.BooleanField(1, required=True)


@Cached(
    PickledMemCache(),  # Since the return values are < 1MB.
    expire_time=ANALYSIS_CACHE_TIME)
def _AsyncProcessFailureAnalysisRequests(builds):
  """Pushes a task on the backend to process requests of failure analysis."""
  target = appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND)
  payload = json.dumps({'builds': builds})
  taskqueue.add(
      url=constants.WATERFALL_PROCESS_FAILURE_ANALYSIS_REQUESTS_URL,
      payload=payload,
      target=target,
      queue_name=constants.WATERFALL_FAILURE_ANALYSIS_REQUEST_QUEUE)
  # Needed for @Cached to work, but ignored by caller.
  return 'Only semantically None.'


def _ValidateOauthUser():
  """Validates the oauth user and raises an exception if not authorized.
  Returns:
    A tuple (user_email, is_admin).
    user_email (str): The email address of the oauth user.
    is_admin (bool): True if the oauth user is an Admin.

  Raises:
    endpoints.UnauthorizedException if the user has no permission.
  """
  try:
    return acl.ValidateOauthUserForNewAnalysis()
  except exceptions.UnauthorizedException as e:
    raise endpoints.UnauthorizedException('Unauthorized: %s' % e.message)


# Create a Cloud Endpoints API.
# https://cloud.google.com/appengine/docs/python/endpoints/create_api
@endpoints.api(name='findit', version='v1', description='FindIt API')
class FindItApi(remote.Service):
  """FindIt API v1."""

  def _GetAdditionalInformationForCL(self, repo_name, revision, confidences,
                                     build, reference_build_key):
    """Gets additional information for a cl.

    Currently additional information contains:
        confidence of the result;
        approaches that found this cl: HEURISTIC, TRY_JOB or both;
        revert_cl_url if the cl has been reverted by Findit;
        if the revert has been committed.
    """
    additional_info = {}

    cl = WfSuspectedCL.Get(repo_name, revision)
    if not cl:
      return additional_info

    master_name = buildbot.GetMasterNameFromUrl(build.master_url)
    builder_name = build.builder_name
    current_build = build.build_number

    # If the CL is found by a try job, only the first failure will be recorded.
    # So we might need to go to the first failure to get CL information.
    build_info = cl.GetBuildInfo(master_name, builder_name, current_build)
    first_build_info = None if not reference_build_key else cl.GetBuildInfo(
        *BaseBuildModel.GetBuildInfoFromId(reference_build_key))
    additional_info['confidence'], additional_info['cl_approach'] = (
        suspected_cl_util.GetSuspectedCLConfidenceScoreAndApproach(
            confidences, build_info, first_build_info))

    # Gets the revert_cl_url for the CL if there is one.
    if cl.revert_cl_url:
      additional_info['revert_cl_url'] = cl.revert_cl_url

    additional_info['revert_committed'] = (
        cl.revert_submission_status == analysis_status.COMPLETED)

    return additional_info

  def _GenerateBuildFailureAnalysisResult(
      self,
      build,
      step_name,
      suspected_cls_in_result=None,
      first_failure=None,
      test_name=None,
      analysis_approach=_AnalysisApproach.HEURISTIC,
      confidences=None,
      try_job_status=None,
      is_flaky_test=False,
      reference_build_key=None,
      has_findings=True,
      is_finished=True,
      is_supported=True):

    suspected_cls_in_result = suspected_cls_in_result or []
    suspected_cls = []
    for suspected_cl in suspected_cls_in_result:
      repo_name = suspected_cl['repo_name']
      revision = suspected_cl['revision']
      commit_position = suspected_cl['commit_position']
      additional_info = self._GetAdditionalInformationForCL(
          repo_name, revision, confidences, build, reference_build_key)
      if additional_info.get('cl_approach'):
        cl_approach = (
            _AnalysisApproach.HEURISTIC if
            additional_info['cl_approach'] == analysis_approach_type.HEURISTIC
            else _AnalysisApproach.TRY_JOB)
      else:
        cl_approach = analysis_approach

      suspected_cls.append(
          _SuspectedCL(
              repo_name=repo_name,
              revision=revision,
              commit_position=commit_position,
              confidence=additional_info.get('confidence'),
              analysis_approach=cl_approach,
              revert_cl_url=additional_info.get('revert_cl_url'),
              revert_committed=additional_info.get('revert_committed')))

    return _BuildFailureAnalysisResult(
        master_url=build.master_url,
        builder_name=build.builder_name,
        build_number=build.build_number,
        step_name=step_name,
        is_sub_test=test_name is not None,
        test_name=test_name,
        first_known_failed_build_number=first_failure,
        suspected_cls=suspected_cls,
        analysis_approach=analysis_approach,
        try_job_status=try_job_status,
        is_flaky_test=is_flaky_test,
        has_findings=has_findings,
        is_finished=is_finished,
        is_supported=is_supported)

  def _GetStatusAndCulpritFromTryJob(self,
                                     try_job,
                                     swarming_task,
                                     build_failure_type,
                                     step_name,
                                     test_name=None):
    """Returns the culprit found by try-job for the given step or test."""

    if swarming_task and swarming_task.status in (analysis_status.PENDING,
                                                  analysis_status.RUNNING):
      return _TryJobStatus.RUNNING, None

    if not try_job or try_job.failed:
      return _TryJobStatus.FINISHED, None

    if not try_job.completed:
      return _TryJobStatus.RUNNING, None

    if build_failure_type == failure_type.COMPILE:
      if not try_job.compile_results:  # pragma: no cover.
        return _TryJobStatus.FINISHED, None
      return (_TryJobStatus.FINISHED, try_job.compile_results[-1].get(
          'culprit', {}).get(step_name))

    if not try_job.test_results:  # pragma: no cover.
      return _TryJobStatus.FINISHED, None

    if test_name is None:
      step_info = try_job.test_results[-1].get('culprit', {}).get(step_name)
      if not step_info or step_info.get('tests'):  # pragma: no cover.
        # TODO(chanli): For some steps like checkperms/sizes/etc, the culprit
        # finding try-job might have test-level results.
        return _TryJobStatus.FINISHED, None
      return _TryJobStatus.FINISHED, step_info

    ref_name = (
        swarming_task.parameters.get('ref_name')
        if swarming_task and swarming_task.parameters else None)
    return (_TryJobStatus.FINISHED,
            try_job.test_results[-1].get('culprit', {}).get(
                ref_name or step_name, {}).get('tests', {}).get(test_name))

  def _CheckIsFlaky(self, swarming_task, test_name):
    """Checks if the test is flaky."""
    if not swarming_task or not swarming_task.classified_tests:
      return False

    return test_name in swarming_task.classified_tests.get('flaky_tests', [])

  def _PopulateResult(self,
                      results,
                      build,
                      step_name,
                      build_failure_type=None,
                      heuristic_result=None,
                      confidences=None,
                      reference_build_key=None,
                      swarming_task=None,
                      try_job=None,
                      test_name=None,
                      has_findings=True,
                      is_finished=True,
                      is_supported=True):
    """Appends an analysis result for the given step or test.

    Try-job results are always given priority over heuristic results.
    """
    if not has_findings or not is_finished:
      results.append(
          self._GenerateBuildFailureAnalysisResult(
              build,
              step_name,
              has_findings=has_findings,
              is_finished=is_finished,
              is_supported=is_supported))
      return

    # Default to heuristic analysis.
    suspected_cls = heuristic_result['suspected_cls']
    analysis_approach = _AnalysisApproach.HEURISTIC

    # Check if the test is flaky.
    is_flaky_test = self._CheckIsFlaky(swarming_task, test_name)

    if is_flaky_test:
      suspected_cls = []
      try_job_status = _TryJobStatus.FINISHED  # There will be no try job.
    else:
      # Check analysis result from try-job.
      try_job_status, culprit = self._GetStatusAndCulpritFromTryJob(
          try_job,
          swarming_task,
          build_failure_type,
          step_name,
          test_name=test_name)
      if culprit:
        suspected_cls = [culprit]
        analysis_approach = _AnalysisApproach.TRY_JOB

    if not is_flaky_test and not suspected_cls:
      # No findings for the test.
      has_findings = False

    if try_job_status == _TryJobStatus.RUNNING:
      is_finished = False

    results.append(
        self._GenerateBuildFailureAnalysisResult(
            build,
            step_name,
            suspected_cls,
            heuristic_result['first_failure'],
            test_name,
            analysis_approach,
            confidences,
            try_job_status,
            is_flaky_test,
            reference_build_key,
            has_findings,
            is_finished,
            is_supported=is_supported))

  def _GetAllSwarmingTasks(self, failure_result_map):
    """Returns all swarming tasks related to one build.

    Args:
      A dict to map each step/test with the key to the build when it failed the
      first time.
      {
          'step1': 'm/b/1',
          'step2': {
              'test1': 'm/b/1',
              'test2': 'm/b/2'
          }
      }

    Returns:
      A dict of swarming tasks like below:
      {
          'step1': {
              'm/b/1': WfSwarmingTask(
                  key=Key('WfBuild', 'm/b/1', 'WfSwarmingTask', 'step1'),...)
          },
          ...
      }
    """
    if not failure_result_map:
      return {}

    swarming_tasks = defaultdict(dict)
    for step_name, step_map in failure_result_map.iteritems():
      if isinstance(step_map, basestring):
        swarming_tasks[step_name][step_map] = (
            WfSwarmingTask.Get(
                *BaseBuildModel.GetBuildInfoFromId(step_map),
                step_name=step_name))
      else:
        for task_key in step_map.values():
          if not swarming_tasks[step_name].get(task_key):
            swarming_tasks[step_name][task_key] = (
                WfSwarmingTask.Get(
                    *BaseBuildModel.GetBuildInfoFromId(task_key),
                    step_name=step_name))

    return swarming_tasks

  def _GetAllTryJobs(self, failure_result_map):
    """Returns all try jobs related to one build.

    Args:
      A dict to map each step/test with the key to the build when it failed the
      first time.
      {
          'step1': 'm/b/1',
          'step2': {
              'test1': 'm/b/1',
              'test2': 'm/b/2'
          }
      }

    Returns:
      A dict of try jobs like below:
      {
          'm/b/1': WfTryJob(
              key=Key('WfBuild', 'm/b/1'),...)
          ...
      }
    """
    if not failure_result_map:
      return {}

    try_jobs = {}
    for step_map in failure_result_map.values():
      if isinstance(step_map, basestring):
        try_jobs[step_map] = WfTryJob.Get(*step_map.split('/'))
      else:
        for task_key in step_map.values():
          if not try_jobs.get(task_key):
            try_jobs[task_key] = WfTryJob.Get(*task_key.split('/'))

    return try_jobs

  def _GetSwarmingTaskAndTryJobForFailure(
      self, step_name, test_name, failure_result_map, swarming_tasks, try_jobs):
    """Gets swarming task and try job for the specific step/test."""
    if not failure_result_map:
      return None, None, None

    if test_name:
      try_job_key = failure_result_map.get(step_name, {}).get(test_name)
    else:
      try_job_key = failure_result_map.get(step_name)

    # Gets the swarming task for the test.
    swarming_task = swarming_tasks.get(step_name, {}).get(try_job_key)

    # Get the try job for the step/test.
    try_job = try_jobs.get(try_job_key)

    return try_job_key, swarming_task, try_job

  def _GenerateResultsForBuild(self, build, heuristic_analysis, results,
                               confidences):

    # Checks has_findings and is_finished for heuristic analysis.
    has_findings = bool(heuristic_analysis and heuristic_analysis.result and
                        not heuristic_analysis.failed)
    is_finished = heuristic_analysis.completed

    if not has_findings:
      # No result.
      for step_name in build.failed_steps:
        is_supported = True  # The step may be analyzed now.
        self._PopulateResult(
            results,
            build,
            step_name,
            has_findings=has_findings,
            is_finished=is_finished,
            is_supported=is_supported)
      return

    steps_with_result = [
        f.get('step_name') for f in heuristic_analysis.result['failures']
    ]
    steps_without_result = [
        step_name for step_name in build.failed_steps
        if step_name not in steps_with_result
    ]

    for step_name in steps_without_result:
      has_findings = False  # No findings for the step.
      is_supported = True  # The step may be analyzed now.
      self._PopulateResult(
          results,
          build,
          step_name,
          has_findings=has_findings,
          is_finished=is_finished,
          is_supported=is_supported)

    swarming_tasks = self._GetAllSwarmingTasks(
        heuristic_analysis.failure_result_map)
    try_jobs = self._GetAllTryJobs(heuristic_analysis.failure_result_map)

    for failure in heuristic_analysis.result['failures']:
      step_name = failure.get('step_name')
      is_supported = failure.get('supported', False)

      if not is_supported:
        has_findings = False
        self._PopulateResult(
            results,
            build,
            step_name,
            has_findings=has_findings,
            is_finished=is_finished,
            is_supported=is_supported)
        continue

      if failure.get('tests'):  # Test-level analysis.
        for test in failure['tests']:
          test_name = test['test_name']
          reference_build_key, swarming_task, try_job = (
              self._GetSwarmingTaskAndTryJobForFailure(
                  step_name, test_name, heuristic_analysis.failure_result_map,
                  swarming_tasks, try_jobs))
          self._PopulateResult(
              results,
              build,
              step_name,
              heuristic_analysis.failure_type,
              test,
              confidences,
              reference_build_key,
              swarming_task,
              try_job,
              test_name=test_name)
      else:
        reference_build_key, swarming_task, try_job = (
            self._GetSwarmingTaskAndTryJobForFailure(
                step_name, None, heuristic_analysis.failure_result_map,
                swarming_tasks, try_jobs))
        self._PopulateResult(
            results, build, step_name, heuristic_analysis.failure_type, failure,
            confidences, reference_build_key, swarming_task, try_job)

  @gae_ts_mon.instrument_endpoint()
  @endpoints.method(
      _BuildFailureCollection,
      _BuildFailureAnalysisResultCollection,
      path='buildfailure',
      name='buildfailure')
  def AnalyzeBuildFailures(self, request):
    """Returns analysis results for the given build failures in the request.

    Analysis of build failures will be triggered automatically on demand.

    Args:
      request (_BuildFailureCollection): A list of build failures.

    Returns:
      _BuildFailureAnalysisResultCollection
      A list of analysis results for the given build failures.
    """
    _ValidateOauthUser()

    results = []
    supported_builds = []
    confidences = SuspectedCLConfidence.Get()

    for build in request.builds:
      master_name = buildbot.GetMasterNameFromUrl(build.master_url)
      if not (master_name and waterfall_config.MasterIsSupported(master_name)):
        logging.info('%s/%s/%s is not supported', build.master_url,
                     build.builder_name, build.build_number)
        continue

      supported_builds.append({
          'master_name': master_name,
          'builder_name': build.builder_name,
          'build_number': build.build_number,
          'failed_steps': sorted(build.failed_steps),
      })

      # If the build failure was already analyzed and a new analysis is
      # scheduled to analyze new failed steps, the returned WfAnalysis will
      # still have the result from last completed analysis.
      # If there is no analysis yet, no result is returned.
      heuristic_analysis = WfAnalysis.Get(master_name, build.builder_name,
                                          build.build_number)
      if not heuristic_analysis:
        continue

      self._GenerateResultsForBuild(build, heuristic_analysis, results,
                                    confidences)

    logging.info('%d build failure(s), while %d are supported',
                 len(request.builds), len(supported_builds))
    try:
      supported_builds.sort()
      _AsyncProcessFailureAnalysisRequests(supported_builds)
    except Exception:  # pragma: no cover.
      # If we fail to post a task to the task queue, we ignore and wait for next
      # request.
      logging.exception('Failed to add analysis request to task queue: %s',
                        repr(supported_builds))

    return _BuildFailureAnalysisResultCollection(results=results)

  @gae_ts_mon.instrument_endpoint()
  @endpoints.method(_Flake, _FlakeAnalysis, path='flake', name='flake')
  def AnalyzeFlake(self, request):
    """Analyze a flake on Commit Queue. Currently only supports flaky tests."""
    user_email, is_admin = _ValidateOauthUser()

    def CreateFlakeAnalysisRequest(flake):
      analysis_request = FlakeAnalysisRequest.Create(flake.name, flake.is_step,
                                                     flake.bug_id)
      for step in flake.build_steps:
        analysis_request.AddBuildStep(step.master_name, step.builder_name,
                                      step.build_number, step.step_name,
                                      time_util.GetUTCNow())
      return analysis_request

    flake_analysis_request = CreateFlakeAnalysisRequest(request)
    logging.info('Flake report: %s', flake_analysis_request)

    try:
      AsyncProcessFlakeReport(flake_analysis_request, user_email, is_admin)
      queued = True
    except Exception:
      # Ignore the report when fail to queue it for async processing.
      queued = False
      logging.exception('Failed to queue flake report for async processing')

    return _FlakeAnalysis(queued=queued)
