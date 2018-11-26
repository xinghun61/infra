# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Functions to assist in notifying flake culprits."""

import logging
import textwrap

from google.appengine.ext import ndb

from infra_api_clients.codereview import codereview_util

from common.waterfall import failure_type
from libs import analysis_status
from libs import floating_point_util
from libs import time_util
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from services import constants
from services import culprit_action
from services import gerrit
from services import git
from services.flake_failure import flake_constants
from services.flake_failure import pass_rate_util
from services.parameters import CreateRevertCLParameters
from services.parameters import SubmitRevertCLParameters
from waterfall import suspected_cl_util
from waterfall import waterfall_config

_NOTIFICATION_MESSAGE_TEMPLATE = textwrap.dedent("""
Findit (https://goo.gl/kROfz5) identified this CL at revision {} as the culprit
for introducing flakiness in the tests as shown on:
https://findit-for-me.appspot.com/waterfall/flake/flake-culprit?key={}

If the results are correct, please either revert this CL, disable, or fix the
flaky test.""")

_NOTIFICATION_WITH_BUG_TEMPLATE = textwrap.dedent("""
{}

Bug: https://bugs.chromium.org/p/chromium/issues/detail?id={}
""")


def _GenerateMessageText(culprit, bug_id):
  """Generates the body to notify a culprit with.

  Args:
    culprit (FlakeCulprit): The culprit to extract display information from and
        eventually notify.
    bug_id (int): An optional bug to include in the notification text. Can be
        None if not to be included.

  Returns:
    message (str): The body of the notification to send.
  """
  main_message = _NOTIFICATION_MESSAGE_TEMPLATE.format(
      culprit.commit_position or culprit.revision, culprit.key.urlsafe())

  if bug_id is None:
    return main_message

  return _NOTIFICATION_WITH_BUG_TEMPLATE.format(main_message, bug_id)


def AbortCreateAndSubmitRevert(parameters, runner_id):
  """Sets the proper fields for an autorevert abort."""
  analysis = ndb.Key(urlsafe=parameters.analysis_urlsafe_key).get()
  assert analysis
  culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
  assert culprit

  changed = False

  if culprit.revert_pipeline_id == runner_id:
    if (culprit.revert_status and
        culprit.revert_status != analysis_status.COMPLETED):
      culprit.revert_status = analysis_status.ERROR
      changed = True

  if culprit.submit_revert_pipeline_id == runner_id:
    if (culprit.revert_submission_status and
        culprit.revert_submission_status != analysis_status.COMPLETED):
      culprit.revert_submission_status = analysis_status.ERROR
      changed = True

  if changed:
    culprit.revert_pipeline_id = None
    culprit.submit_revert_pipeline_id = None
    culprit.put()


def CreateAndSubmitRevert(parameters, runner_id):
  """Wraps the creation and submission of autoreverts for flaky tests."""
  analysis = ndb.Key(urlsafe=parameters.analysis_urlsafe_key).get()
  assert analysis
  culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
  assert culprit

  # TODO(crbug.com/907675): Create, but not auto commit reverts for some
  # culprits.

  if not UnderLimitForAutorevert():
    analysis.LogInfo('Not autoreverting since limit has been reached.')
    return False

  # Verify the conditions for revert are satisfied.
  if not CanRevertForAnalysis(analysis):
    analysis.LogInfo('Not reverting: CanRevertForAnalysis returned false.')
    return False

  # Create the revert, and check if it succeeded. If it succeeded, then
  # continue on and submit it.
  revert_culprit_parameters = CreateRevertCLParameters(
      cl_key=culprit.key.urlsafe(),
      build_key=parameters.build_key,
      failure_type=failure_type.FLAKY_TEST)
  revert_status = culprit_action.RevertCulprit(revert_culprit_parameters,
                                               runner_id)
  if revert_status != constants.CREATED_BY_FINDIT:
    analysis.LogInfo(
        'Not reverting: RevertCulprit wasn\'t able to create a revert.')
    return False

  submit_revert_paramters = SubmitRevertCLParameters(
      cl_key=culprit.key.urlsafe(),
      revert_status=revert_status,
      failure_type=failure_type.FLAKY_TEST)
  submit_revert_status = culprit_action.CommitRevert(submit_revert_paramters,
                                                     runner_id)
  if submit_revert_status != constants.COMMITTED:
    analysis.LogInfo(
        'Not reverting: CommitRevert wasn\'t able to submit the revert')
    analysis.Update(has_created_autorevert=True)
    return False

  analysis.Update(
      has_created_autorevert=True,
      has_submitted_autorevert=True,
      autorevert_submission_time=time_util.GetUTCNow())
  return True


def UnderLimitForAutorevert():
  """Returns True if currently under the limit for autoreverts."""
  action_settings = waterfall_config.GetActionSettings()

  # Do not auto commit revert if not configured to do so.
  limit = action_settings.get('auto_commit_revert_daily_threshold_flake')

  query = MasterFlakeAnalysis.query(
      MasterFlakeAnalysis.autorevert_submission_time >=
      time_util.GetMostRecentUTCMidnight(),
      MasterFlakeAnalysis.has_submitted_autorevert == True)

  return query.count(limit) < limit


def CanRevertForAnalysis(analysis):
  """Returns True if the analysis can be reverted, false otherwise.

  Several conditions must be satisfied for this to happen:
  1. There must be sufficient confidence in the culprit.
  2. The test must be newly-added.
  3. The commit must have happened in the last 24 hours. This is to reduce the
     likelyhood that other changes have landed since the culprit that may depend
     on it such that reverting it would introduce further breakages.
  4. TODO(crbug.com/872839): Check the test is still flaky in a recent build
     before reverting.
  """
  culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
  assert culprit, 'Culprit unexpectedly missing from datastore'

  previous_data_point = analysis.FindMatchingDataPointWithCommitPosition(
      culprit.commit_position - 1)

  if (analysis.confidence_in_culprit is None or
      not floating_point_util.AlmostEquals(analysis.confidence_in_culprit,
                                           1.0)):
    analysis.LogInfo('Cannot revert culprit for an analysis with insufficient '
                     'confidence {}'.format(analysis.confidence_in_culprit))
    return False

  if (previous_data_point is None or not floating_point_util.AlmostEquals(
      previous_data_point.pass_rate, flake_constants.PASS_RATE_TEST_NOT_FOUND)):
    analysis.LogInfo('Cannot revert non-newly-added tests')
    return False

  if not git.ChangeCommittedWithinTime(culprit.revision):
    analysis.LogInfo('Cannot revert culprit > 24 hours old')
    return False

  return True


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


def IsConfiguredToNotifyCulprits():
  action_settings = waterfall_config.GetActionSettings()
  return action_settings.get('cr_notification_should_notify_flake_culprit',
                             False)


def NotifyCulprit(culprit, bug_id):
  """Sends a notification to a code review page.

  Args:
    culprit (FlakeCulprit): The culprit identified to have introduced flakiness.
    bud_id (int): An optional bug id to include in the notification. Pass None
        if not specified.

  Returns:
    Bool indicating whether a notification was sent.
  """
  assert culprit

  repo_name = culprit.repo_name
  revision = culprit.revision
  culprit_info = git.GetCodeReviewInfoForACommit(repo_name, revision)

  review_server_host = culprit_info.get('review_server_host')
  review_change_id = culprit_info.get('review_change_id')

  code_review_settings = waterfall_config.GetCodeReviewSettings()
  codereview = codereview_util.GetCodeReviewForReview(review_server_host,
                                                      code_review_settings)
  sent = False

  if codereview and review_change_id:
    message = _GenerateMessageText(culprit, bug_id)
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
     4. Never send if there is insufficient confidence that the culprit is
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

  # Check confidence in culprit.
  if analysis.confidence_in_culprit < GetMinimumConfidenceToNotifyCulprits():
    analysis.LogInfo('Skipping sending notification to code review due to '
                     'insufficient confidence')
    return False

  return True
