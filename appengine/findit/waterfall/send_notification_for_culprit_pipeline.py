# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import textwrap

from google.appengine.ext import ndb

from gae_libs.pipeline_wrapper import BasePipeline
from infra_api_clients.codereview import codereview_util
from libs import analysis_status as status
from libs import time_util
from model.wf_config import FinditConfig
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import build_util
from waterfall import create_revert_cl_pipeline
from waterfall import suspected_cl_util
from waterfall import waterfall_config


@ndb.transactional
def _ShouldSendNotification(
    repo_name, revision, build_num_threshold, force_notify):
  """Returns True if a notification for the culprit should be sent.

  Send notification only when:
    1. It was not processed yet.
    2. The culprit is for multiple failures in different builds to avoid false
      positive due to flakiness.

  Any new criteria for deciding when to notify should be implemented within this
  function.

  Args:
    repo_name, revision (str): Uniquely identify the revision to notify about.
    build_num_threshold (int): The number of builds the culprit needs to cause
        to fail before we notify. (To avoid false notifications for flake)
    force_notify (bool): If we should skip the fail number threshold check.

  Returns:
    A boolean indicating whether we should send the notification.

  """
  # TODO (chanli): Add check for if confidence for the culprit is
  # over threshold.
  culprit = WfSuspectedCL.Get(repo_name, revision)
  assert culprit

  if culprit.cr_notification_processed:
    return False

  if force_notify or len(culprit.builds) >= build_num_threshold:
    culprit.cr_notification_status = status.RUNNING
    culprit.put()
    return True
  return False


@ndb.transactional
def _UpdateNotificationStatus(repo_name, revision, new_status):
  culprit = WfSuspectedCL.Get(repo_name, revision)
  culprit.cr_notification_status = new_status
  if culprit.cr_notified:
    culprit.cr_notification_time = time_util.GetUTCNow()
  culprit.put()


def _SendNotificationForCulprit(
    repo_name, revision, commit_position, review_server_host, change_id,
    revert_status):
  code_review_settings = FinditConfig().Get().code_review_settings
  codereview = codereview_util.GetCodeReviewForReview(
      review_server_host, code_review_settings)
  sent = False
  if codereview and change_id:
    # Occasionally, a commit was not uploaded for code-review.
    culprit = WfSuspectedCL.Get(repo_name, revision)

    action = 'identified'
    if revert_status == create_revert_cl_pipeline.CREATED_BY_SHERIFF:
      action = 'confirmed'

    message = textwrap.dedent("""
    Findit (https://goo.gl/kROfz5) %s this CL at revision %s as the culprit for
    failures in the build cycles as shown on:
    https://findit-for-me.appspot.com/waterfall/culprit?key=%s""") % (
        action, commit_position or revision, culprit.key.urlsafe())
    sent = codereview.PostMessage(change_id, message)
  else:
    logging.error('No code-review url for %s/%s', repo_name, revision)

  _UpdateNotificationStatus(repo_name, revision,
                            status.COMPLETED if sent else status.ERROR)
  return sent


class SendNotificationForCulpritPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(
      self, master_name, builder_name, build_number, repo_name, revision,
      force_notify, revert_status=None):

    # This information is not needed at the moment.
    # TODO(robertocn): Remove these arguments if we won't need them for
    # notifications once auto-revert is enabled.
    _build_information = [master_name, builder_name, build_number]

    if revert_status == create_revert_cl_pipeline.CREATED_BY_FINDIT:
      # Already notified when revert, bail out.
      return False

    if revert_status == create_revert_cl_pipeline.CREATED_BY_SHERIFF:
      force_notify = True

    action_settings = waterfall_config.GetActionSettings()
    # Set some impossible default values to prevent notification by default.
    build_num_threshold = action_settings.get(
        'cr_notification_build_threshold', 100000)

    culprit_info = suspected_cl_util.GetCulpritInfo(
        repo_name, revision)
    commit_position = culprit_info['commit_position']
    review_server_host = culprit_info['review_server_host']
    review_change_id = culprit_info['review_change_id']

    if not _ShouldSendNotification(
        repo_name, revision, build_num_threshold, force_notify):
      return False
    return _SendNotificationForCulprit(
        repo_name, revision, commit_position, review_server_host,
        review_change_id, revert_status)
