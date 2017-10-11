# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from common.waterfall import failure_type
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import time_util
from model import analysis_approach_type
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import build_util


def GetCLInfo(cl_info_str):
  """Gets CL's repo_name and revision."""
  return cl_info_str.split('/')


def _GetsStatusFromSameFailure(builds, failures):
  for build in builds.values():
    if build['status'] is not None and build['failures'] == failures:
      return build['status']
  return None


@ndb.transactional
def UpdateSuspectedCL(repo_name, revision, commit_position, approach,
                      master_name, builder_name, build_number, cl_failure_type,
                      failures, top_score):

  suspected_cl = (WfSuspectedCL.Get(repo_name, revision) or
                  WfSuspectedCL.Create(repo_name, revision, commit_position))

  if not suspected_cl.identified_time:  # pragma: no cover.
    suspected_cl.identified_time = time_util.GetUTCNow()

  suspected_cl.updated_time = time_util.GetUTCNow()

  if approach not in suspected_cl.approaches:
    suspected_cl.approaches.append(approach)
  if cl_failure_type not in suspected_cl.failure_type:
    suspected_cl.failure_type.append(cl_failure_type)

  build_key = build_util.CreateBuildId(master_name, builder_name, build_number)
  if build_key not in suspected_cl.builds:
    suspected_cl.builds[build_key] = {
        'approaches': [approach],
        'failure_type': cl_failure_type,
        'failures': failures,
        'status': _GetsStatusFromSameFailure(suspected_cl.builds, failures),
        'top_score': top_score
    }
  else:
    build = suspected_cl.builds[build_key]
    if approach not in build['approaches']:
      build['approaches'].append(approach)

  suspected_cl.put()


def _RoundConfidentToInteger(confidence):
  return int(round(confidence * 100))


def GetSuspectedCLConfidenceScore(confidences, cl_from_analyzed_build):
  if not confidences or not cl_from_analyzed_build:
    return None

  if cl_from_analyzed_build['failure_type'] == failure_type.COMPILE:
    if sorted(cl_from_analyzed_build['approaches']) == sorted(
        [analysis_approach_type.HEURISTIC, analysis_approach_type.TRY_JOB]):
      return _RoundConfidentToInteger(
          confidences.compile_heuristic_try_job.confidence)
    elif cl_from_analyzed_build['approaches'] == [
        analysis_approach_type.TRY_JOB
    ]:
      return _RoundConfidentToInteger(confidences.compile_try_job.confidence)
    elif (cl_from_analyzed_build['approaches'] == [
        analysis_approach_type.HEURISTIC
    ] and cl_from_analyzed_build['top_score']):
      for confidences_info in confidences.compile_heuristic:
        if confidences_info.score == cl_from_analyzed_build['top_score']:
          return _RoundConfidentToInteger(confidences_info.confidence)
    return None
  else:
    if sorted(cl_from_analyzed_build['approaches']) == sorted(
        [analysis_approach_type.HEURISTIC, analysis_approach_type.TRY_JOB]):
      return _RoundConfidentToInteger(
          confidences.test_heuristic_try_job.confidence)
    elif cl_from_analyzed_build['approaches'] == [
        analysis_approach_type.TRY_JOB
    ]:
      return _RoundConfidentToInteger(confidences.test_try_job.confidence)
    elif (cl_from_analyzed_build['approaches'] == [
        analysis_approach_type.HEURISTIC
    ] and cl_from_analyzed_build['top_score']):
      for confidences_info in confidences.test_heuristic:
        if confidences_info.score == cl_from_analyzed_build['top_score']:
          return _RoundConfidentToInteger(confidences_info.confidence)
    return None


def _HasNewFailures(current_failures, new_failures):
  """Checks if there are any new failures in the current build."""
  if current_failures == new_failures:
    return False

  for step, tests in current_failures.iteritems():
    if not new_failures.get(step):  # New step.
      return True

    for test in tests:
      if not test in new_failures[step]:  # New test.
        return True

  return False


def GetSuspectedCLConfidenceScoreAndApproach(
    confidences, cl_from_analyzed_build, cl_from_first_failed_build):
  if not confidences or (not cl_from_analyzed_build and
                         not cl_from_first_failed_build):
    return None, None

  if (cl_from_first_failed_build and
      (not cl_from_analyzed_build or not _HasNewFailures(
          cl_from_analyzed_build.get('failures'),
          cl_from_first_failed_build.get('failures')))):
    # For non-first-time failures, the try job result is not recorded.
    # If there is no new failures in current build, use first failed build to
    # make sure the confidence score is correct.
    cl_from_analyzed_build = cl_from_first_failed_build

  confidence = GetSuspectedCLConfidenceScore(confidences,
                                             cl_from_analyzed_build)
  approach = (
      analysis_approach_type.TRY_JOB
      if analysis_approach_type.TRY_JOB in cl_from_analyzed_build['approaches']
      else analysis_approach_type.HEURISTIC)

  return confidence, approach


def GetCulpritInfo(repo_name, revision):
  """Returns culprit info of the given revision.

  Returns commit position, code-review url, host and change_id.
  """
  # TODO(stgao): get repo url at runtime based on the given repo name.
  # unused arg - pylint: disable=W0612,W0613
  repo = CachedGitilesRepository(
      FinditHttpClient(), 'https://chromium.googlesource.com/chromium/src.git')
  change_log = repo.GetChangeLog(revision)
  return {
      'commit_position': change_log.commit_position,
      'code_review_url': change_log.code_review_url,
      'review_server_host': change_log.review_server_host,
      'review_change_id': change_log.review_change_id,
      'author': change_log.author.ToDict(),
  }


@ndb.transactional
def UpdateCulpritNotificationStatus(culprit_urlsafe_key, new_status):
  """Updates a culprit (WfSuspectedCL, FalkeCulprit)'s status.

  Args:
    culprit_urlsafe_key (str): A urlsafe key corresponding to the culprit to
        update.
  """
  culprit = ndb.Key(urlsafe=culprit_urlsafe_key).get()
  assert culprit

  culprit.cr_notification_status = new_status
  if culprit.cr_notified:
    culprit.cr_notification_time = time_util.GetUTCNow()
  culprit.put()
