# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions to assist in notifying flake culprits."""

import logging
import textwrap

from google.appengine.ext import ndb

from infra_api_clients.codereview import codereview_util
from libs import analysis_status
from services.flake_failure import data_point_util
from services.flake_failure import pass_rate_util
from waterfall import suspected_cl_util
from waterfall import waterfall_config
from waterfall.flake import flake_constants

_NOTIFICATION_MESSAGE_TEMPLATE = textwrap.dedent("""
Findit (https://goo.gl/kROfz5) identified this CL at revision {} as the culprit
for introducing flakiness in the tests as shown on:
https://findit-for-me.appspot.com/waterfall/flake/flake-culprit?key={}

If the results are correct, please either revert this CL, disable, or fix the
flaky test.""")


def CulpritAddedNewFlakyTest(analysis, culprit_commit_position):
  """Checks if the culprit was the result of a newly-added test in an analayis,

      Note in analyses, the culprit is never the first data point when ordered
      by commit position. In order to determine a culprit, a history of stable
      points must precede a culprit in order to identify it as such.

  Args:
    analysis (MasterFlakeAnalysis): The analysis that led to the culprit.
    culprit (FlakeCulprit): The culprit itself.

  Returns:
    Boolean whether the culprit was a newly-added test.
  """
  assert len(analysis.data_points) > 1
  culprit_data_point = analysis.FindMatchingDataPointWithCommitPosition(
      culprit_commit_position)
  assert culprit_data_point
  assert culprit_data_point.pass_rate
  previous_data_point = analysis.FindMatchingDataPointWithCommitPosition(
      culprit_commit_position - 1)
  assert previous_data_point
  assert previous_data_point.pass_rate is not None

  return pass_rate_util.TestDoesNotExist(previous_data_point.pass_rate)


def GetMinimumConfidenceToNotifyCulprits():
  check_flake_settings = waterfall_config.GetCheckFlakeSettings()
  return check_flake_settings.get(
      'minimum_confidence_to_update_cr',
      flake_constants.DEFAULT_MINIMUM_CONFIDENCE_SCORE_TO_UPDATE_CR)


def HasSeriesOfFullyStablePointsPrecedingCulprit(analysis):
  """Checks for a minimum number of fully-stable points before the culprit."""
  culprit_urlsafe_key = analysis.culprit_urlsafe_key
  assert culprit_urlsafe_key

  culprit = ndb.Key(urlsafe=culprit_urlsafe_key).get()
  assert culprit

  ordered_data_points = sorted(
      analysis.data_points, key=lambda k: k.commit_position)
  required_number_of_stable_points = (
      flake_constants.REQUIRED_NUMBER_OF_STABLE_POINTS_BEFORE_CULPRIT)
  culprit_commit_position = culprit.commit_position

  return data_point_util.HasSeriesOfFullyStablePointsPrecedingCommitPosition(
      ordered_data_points, culprit_commit_position,
      required_number_of_stable_points)


def IsConfiguredToNotifyCulprits():
  action_settings = waterfall_config.GetActionSettings()
  return action_settings.get('cr_notification_should_notify_flake_culprit',
                             False)


def NotifyCulprit(culprit):
  """Sends a notification to a code review page.

  Args:
    culprit (FlakeCulprit): The culprit identified to have introduced flakiness.

  Returns:
    Bool indicating whether a notification was sent.
  """
  assert culprit

  repo_name = culprit.repo_name
  revision = culprit.revision
  culprit_info = suspected_cl_util.GetCulpritInfo(repo_name, revision)

  review_server_host = culprit_info.get('review_server_host')
  review_change_id = culprit_info.get('review_change_id')

  code_review_settings = waterfall_config.GetCodeReviewSettings()
  codereview = codereview_util.GetCodeReviewForReview(review_server_host,
                                                      code_review_settings)
  sent = False

  if codereview and review_change_id:
    message = _NOTIFICATION_MESSAGE_TEMPLATE.format(culprit.commit_position or
                                                    culprit.revision,
                                                    culprit.key.urlsafe())
    sent = codereview.PostMessage(review_change_id, message)
  else:
    # Occasionally, a commit was not uploaded for code-review.
    logging.error('No code-review url for %s/%s', culprit.repo_name,
                  culprit.revision)

  status = analysis_status.COMPLETED if sent else analysis_status.ERROR
  suspected_cl_util.UpdateCulpritNotificationStatus(culprit.key.urlsafe(),
                                                    status)
  return sent


@ndb.transactional
def PrepareCulpritForSendingNotification(culprit_urlsafe_key):
  """Prepares a culprit to send a notification.

    This should be done in a transaction to avoid multiple simultaneous
    analyses reaching the same conclusion and sending multiple notifications
    to the same code review should the results become available at the same
    time.

  Args:
    culprit_urlsafe_key (str): The urlsafe key to the culprit to notify.

  Returns:
    (bool) whether a culprit has been set ready to notify.
  """
  culprit = ndb.Key(urlsafe=culprit_urlsafe_key).get()
  assert culprit

  if (culprit.cr_notification_processed or
      culprit.cr_notification_status == analysis_status.RUNNING):
    # Another analysis is already about to send the notification.
    return False

  culprit.cr_notification_status = analysis_status.RUNNING
  culprit.put()
  return True


def ShouldNotifyCulprit(analysis):
  """Determines whether a culprit will be notified.

    Sending notifications should obey the following rules in order:
     1. Never send a notification if Findit is not configured to do so.
     2. Never send if the culprit has already been notified by Findit.
     3. Always send if the culprit introduced a new flaky test.
     4. Never send if the culprit is not preceded by a minimum number of
        fully-passing or fully-failing data points.
     5. Never send if there is insufficient confidence that the culprit is
        indeed responsible.

  Args:
    analysis (MasterFlakeAnalysis): The analysis that identified the culprit.

  Returns:
    bool whether or not the culprit should be notified.
  """
  # Check config.
  if not IsConfiguredToNotifyCulprits():
    analysis.LogInfo('Skipping sending notification to code review due to '
                     'disabled or missing parameter set in action_settings')
    return False

  # Ensure there is a culprit and the culprit's commit position has a
  # corresponding data point in the analysis.
  assert analysis.culprit_urlsafe_key
  culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
  assert culprit

  # Check if this culprit has already been notified.
  if culprit.cr_notification_processed:
    analysis.LogInfo('Skipping sending notification to code review due to '
                     'culprit already being notified')
    return False

  culprit_commit_position = culprit.commit_position
  assert analysis.FindMatchingDataPointWithCommitPosition(
      culprit_commit_position)

  # Always notify culprits for newly-added flaky tests.
  if CulpritAddedNewFlakyTest(analysis, culprit_commit_position):
    analysis.LogInfo('Sending notification to code review due to adding a new '
                     'flaky test')
    return True

  # A series of fully-stable points must precede the culprit.
  if not HasSeriesOfFullyStablePointsPrecedingCulprit(analysis):
    analysis.LogInfo('Skipping sending notification to code review due to '
                     'the likelyhood of it being a false positive')
    return False

  # Check confidence in culprit.
  if analysis.confidence_in_culprit < GetMinimumConfidenceToNotifyCulprits():
    analysis.LogInfo('Skipping sending notification to code review due to '
                     'insufficient confidence')
    return False

  return True
