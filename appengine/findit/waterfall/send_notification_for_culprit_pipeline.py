# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging
import textwrap

from google.appengine.ext import ndb

from common.pipeline_wrapper import BasePipeline
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from gae_libs.http.http_client_appengine import HttpClientAppengine
from infra_api_clients.codereview import codereview_util
from libs import time_util
from model import analysis_status as status
from model.wf_analysis import WfAnalysis
from model.wf_culprit import WfCulprit
from waterfall import build_util
from waterfall import waterfall_config


def _AdditionalCriteriaAllPassed(additional_criteria):
  """Check if the all the additional criteria have passed.

  Checks for individual criterion have been done before this function.
  """
  return all(additional_criteria.values())


@ndb.transactional
def _ShouldSendNotification(
    master_name, builder_name, build_number, repo_name, revision,
    commit_position, build_num_threshold, additional_criteria,
    send_notification_right_now):
  """Returns True if a notification for the culprit should be sent."""
  culprit = (WfCulprit.Get(repo_name, revision) or
             WfCulprit.Create(repo_name, revision, commit_position))
  if [master_name, builder_name, build_number] in culprit.builds:
    return False

  culprit.builds.append([master_name, builder_name, build_number])
  # Send notification only when:
  # 1. It was not processed yet.
  # 2. The culprit is for multiple failures in different builds to avoid false
  #    positive due to flakiness.
  # 3. It is not too late after the culprit was committed.
  #    * Try-job takes too long to complete and the failure got fixed.
  #    * The whole analysis was rerun a long time after the failure occurred.
  should_send = not (culprit.cr_notification_processed or
                     not _AdditionalCriteriaAllPassed(additional_criteria))
  if not send_notification_right_now:
    should_send = should_send and len(culprit.builds) >= build_num_threshold

  if should_send:
    culprit.cr_notification_status = status.RUNNING
  culprit.put()
  return should_send


@ndb.transactional
def _UpdateNotificationStatus(repo_name, revision, new_status):
  culprit = WfCulprit.Get(repo_name, revision)
  culprit.cr_notification_status = new_status
  if culprit.cr_notified:
    culprit.cr_notification_time = time_util.GetUTCNow()
  culprit.put()


def _SendNotificationForCulprit(
    repo_name, revision, commit_position, code_review_url):
  codereview = codereview_util.GetCodeReviewForReview(code_review_url)
  change_id = codereview_util.GetChangeIdForReview(code_review_url)
  sent = False
  if codereview and change_id:
    # Occasionally, a commit was not uploaded for code-review.
    culprit = WfCulprit.Get(repo_name, revision)
    message = textwrap.dedent("""
    FYI: Findit identified this CL at revision %s as the culprit for
    failures in the build cycles as shown on:
    https://findit-for-me.appspot.com/waterfall/culprit?key=%s""") % (
        commit_position or revision, culprit.key.urlsafe())
    sent = codereview.PostMessage(change_id, message)
  else:
    logging.error('No code-review url for %s/%s', repo_name, revision)

  _UpdateNotificationStatus(repo_name, revision,
                            status.COMPLETED if sent else status.ERROR)
  return sent


def _GetCulpritInfo(repo_name, revision):
  """Returns commit position/time and code-review url of the given revision."""
  # TODO(stgao): get repo url at runtime based on the given repo name.
  # unused arg - pylint: disable=W0612,W0613
  repo = CachedGitilesRepository(
      HttpClientAppengine(),
      'https://chromium.googlesource.com/chromium/src.git')
  change_log = repo.GetChangeLog(revision)
  return change_log.commit_position, change_log.code_review_url


def _WithinNotificationTimeLimit(build_end_time, latency_limit_minutes):
  """Returns True if it is still in time to send notification."""
  latency_seconds = (time_util.GetUTCNow() - build_end_time).total_seconds()
  return latency_seconds <= latency_limit_minutes * 60


class SendNotificationForCulpritPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, repo_name, revision,
      send_notification_right_now):
    action_settings = waterfall_config.GetActionSettings()
    # Set some impossible default values to prevent notification by default.
    build_num_threshold = action_settings.get(
        'cr_notification_build_threshold', 100000)
    latency_limit_minutes = action_settings.get(
        'cr_notification_latency_limit_minutes', 1)

    commit_position, code_review_url = _GetCulpritInfo(
        repo_name, revision)
    build_end_time = build_util.GetBuildEndTime(
        master_name, builder_name, build_number)
    within_time_limit = _WithinNotificationTimeLimit(
        build_end_time, latency_limit_minutes)

    # Additional criteria that will help decide if a notification
    # should be sent.
    # TODO (chanli): Add check for if confidence for the culprit is
    # over threshold.
    additional_criteria = {
        'within_time_limit': within_time_limit
    }

    if not _ShouldSendNotification(
      master_name, builder_name, build_number, repo_name,
      revision, commit_position, build_num_threshold, additional_criteria,
      send_notification_right_now):
      return False
    return _SendNotificationForCulprit(
        repo_name, revision, commit_position, code_review_url)
