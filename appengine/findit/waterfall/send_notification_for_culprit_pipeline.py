# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging
import textwrap

from google.appengine.ext import ndb

from common.git_repository import GitRepository
from common.http_client_appengine import HttpClientAppengine as HttpClient
from common.pipeline_wrapper import BasePipeline
from common.rietveld import Rietveld
from model import analysis_status as status
from model.wf_culprit import WfCulprit


@ndb.transactional
def _ShouldSendNotification(
    master_name, builder_name, build_number, repo_name, revision):
  """Returns True if a notification for the culprit should be sent."""
  culprit = (WfCulprit.Get(repo_name, revision) or
             WfCulprit.Create(repo_name, revision))
  if [master_name, builder_name, build_number] in culprit.builds:
    return False

  culprit.builds.append([master_name, builder_name, build_number])
  # Send notification when the culprit is for 2+ failures in two different
  # builds to avoid false positive due to flakiness.
  # TODO(stgao): move to config.
  should_send = not (culprit.cr_notification_processed or
                     len(culprit.builds) < 2)
  if should_send:
    culprit.cr_notification_status = status.RUNNING
  culprit.put()
  return should_send


@ndb.transactional
def _UpdateNotificationStatus(repo_name, revision, new_status):
  culprit = WfCulprit.Get(repo_name, revision)
  culprit.cr_notification_status = new_status
  if culprit.cr_notified:
    culprit.cr_notification_time = datetime.utcnow()
  culprit.put()


def _SendNotificationForCulprit(repo_name, revision):
  # TODO(stgao): get repo url at runtime based on the given repo name.
  repo = GitRepository(
      'https://chromium.googlesource.com/chromium/src.git', HttpClient())
  change_log = repo.GetChangeLog(revision)
  sent = False
  if change_log.code_review_url:
    # Occasionally, a commit was not uploaded for code-review.
    culprit = WfCulprit.Get(repo_name, revision)
    rietveld = Rietveld()
    message = textwrap.dedent("""
    Findit Try-job identified this CL (revision %s) as the culprit for failures
    in the build cycle(s) as shown on:
    https://findit-for-me.appspot.com/waterfall/culprit?key=%s
    """) % (revision, culprit.key.urlsafe())
    sent = rietveld.PostMessage(change_log.code_review_url, message)
  else:
    logging.error('Can not get code-review url for %s/%s', repo_name, revision)

  _UpdateNotificationStatus(repo_name, revision,
                            status.COMPLETED if sent else status.ERROR)
  return sent


class SendNotificationForCulpritPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, repo_name, revision):
    if not _ShouldSendNotification(
      master_name, builder_name, build_number, repo_name, revision):
      return False
    return _SendNotificationForCulprit(repo_name, revision)
