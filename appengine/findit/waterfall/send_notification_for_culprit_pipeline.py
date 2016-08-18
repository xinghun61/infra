# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging
import textwrap

from google.appengine.ext import ndb

from common import time_util
from common.git_repository import GitRepository
from common.http_client_appengine import HttpClientAppengine as HttpClient
from common.pipeline_wrapper import BasePipeline
from common.rietveld import Rietveld
from model import analysis_status as status
from model.wf_culprit import WfCulprit
from waterfall import build_util
from waterfall import waterfall_config


@ndb.transactional
def _ShouldSendNotification(
    master_name, builder_name, build_number, repo_name, revision,
    commit_position, build_num_threshold, time_limit_passed):
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
                     len(culprit.builds) < build_num_threshold or
                     time_limit_passed)
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
  sent = False
  if code_review_url:
    # Occasionally, a commit was not uploaded for code-review.
    culprit = WfCulprit.Get(repo_name, revision)
    rietveld = Rietveld()
    message = textwrap.dedent("""
    FYI: Findit try jobs (rerunning failed compile or tests) identified this CL
    at revision %s as the culprit for failures in the build cycles as shown on:
    https://findit-for-me.appspot.com/waterfall/culprit?key=%s
    """) % (commit_position or revision, culprit.key.urlsafe())
    sent = rietveld.PostMessage(code_review_url, message)
  else:
    logging.error('No code-review url for %s/%s', repo_name, revision)

  _UpdateNotificationStatus(repo_name, revision,
                            status.COMPLETED if sent else status.ERROR)
  return sent


def _GetCulpritInfo(repo_name, revision):
  """Returns commit position/time and code-review url of the given revision."""
  # TODO(stgao): get repo url at runtime based on the given repo name.
  # unused arg - pylint: disable=W0612,W0613
  repo = GitRepository(
      'https://chromium.googlesource.com/chromium/src.git', HttpClient())
  change_log = repo.GetChangeLog(revision)
  return change_log.commit_position, change_log.code_review_url


def _NotificationTimeLimitPassed(build_end_time, latency_limit_minutes):
  """Returns True if it is too late to send notification."""
  latency_seconds = (time_util.GetUTCNow() - build_end_time).total_seconds()
  return latency_seconds > latency_limit_minutes * 60


class SendNotificationForCulpritPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, repo_name, revision):
    action_settings = waterfall_config.GetActionSettings()
    # Set some impossible default values to prevent notification by default.
    build_threshold = action_settings.get(
        'cr_notification_build_threshold', 100000)
    latency_limit_minutes = action_settings.get(
        'cr_notification_latency_limit_minutes', 1)

    commit_position, code_review_url = _GetCulpritInfo(
        repo_name, revision)
    build_end_time = build_util.GetBuildEndTime(
        master_name, builder_name, build_number)
    time_limit_passed = _NotificationTimeLimitPassed(
        build_end_time, latency_limit_minutes)

    if not _ShouldSendNotification(
      master_name, builder_name, build_number, repo_name,
      revision, commit_position, build_threshold, time_limit_passed):
      return False
    return _SendNotificationForCulprit(
        repo_name, revision, commit_position, code_review_url)
