# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import textwrap

from google.appengine.ext import ndb

from gae_libs.pipeline_wrapper import BasePipeline
from infra_api_clients.codereview import codereview_util
from libs import analysis_status as status
from model.wf_config import FinditConfig
from waterfall import suspected_cl_util
from waterfall import waterfall_config
from waterfall.flake import flake_constants
from waterfall.flake import lookback_algorithm

_MESSAGE_TEMPLATE = textwrap.dedent("""
Findit (https://goo.gl/kROfz5) identified this CL at revision %s as the culprit
for introducing flakiness in the tests as shown on:
https://findit-for-me.appspot.com/waterfall/flake/flake-culprit?key=%s""")


def _NewlyAddedTest(analysis, culprit):
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
  data_points = sorted(analysis.data_points, key=lambda k: k.commit_position)
  previous_data_point = data_points[0]

  for data_point in data_points[1:]:
    if data_point.commit_position == culprit.commit_position:
      return (previous_data_point.pass_rate ==
              flake_constants.PASS_RATE_TEST_NOT_FOUND)
    previous_data_point = data_point

  return False


def _HasSeriesOfFullyStablePointsPrecedingCommitPosition(
    data_points, commit_position, required_number_of_stable_points):
  """Checks for a minimum number of fully-stable points before a given commit.

      Fully-stable must also be the same type of stable (for non-newly added
      tests): fully-passing to fully-passing, fully-failing to fully-failing.
      This function should not be responsible to handle newly-added tests.

  Args:
    data_points ([DataPoint]): The list of data points of a MasterFlakeAnalysis.
        data_points is expected to be pre-sorted in ascending order by commit
        position.
    commit_position (int): The commit position to find stable points preceding.
    required_number_of_stable_points (int): The minimum number of data points
        of the same fully-stable type required in order to send a notification
        to a code review.
  """

  def HasSamePassRate(data_point_1, data_point_2):
    return abs(data_point_1.pass_rate - data_point_2.pass_rate) < 0.0000001

  if required_number_of_stable_points > len(data_points):
    return False

  fully_stable_data_points_in_a_row = 0
  previous_data_point = data_points[0]

  for data_point in data_points:
    if data_point.commit_position == commit_position:
      break

    if lookback_algorithm.IsFullyStable(data_point.pass_rate):
      # Only 100% passing or 100% failing can count towards fully-stable.
      if HasSamePassRate(data_point, previous_data_point):
        # Must be the same type of fully-stable in order to count towards the
        # series.
        fully_stable_data_points_in_a_row += 1
      else:
        # A new series of stable passing/failing began. For example, if a series
        # of passes is followed by a failure, begin counting at the failure.
        fully_stable_data_points_in_a_row = 1
    else:
      # A slightly-flaky data point was encuntered. Reset the count.
      fully_stable_data_points_in_a_row = 0

    previous_data_point = data_point

  return fully_stable_data_points_in_a_row >= required_number_of_stable_points


def _HasSeriesOfFullyStablePointsPrecedingCulprit(analysis, culprit):
  """Checks for a minimum number of fully-stable points before the culprit."""
  ordered_data_points = sorted(
      analysis.data_points, key=lambda k: k.commit_position)
  culprit_commit_position = culprit.commit_position
  required_number_of_stable_points = (
      flake_constants.REQUIRED_NUMBER_OF_STABLE_POINTS_BEFORE_CULPRIT)

  return _HasSeriesOfFullyStablePointsPrecedingCommitPosition(
      ordered_data_points, culprit_commit_position,
      required_number_of_stable_points)


@ndb.transactional
def _ShouldSendNotification(analysis, action_settings):
  """Returns True if a notification for the culprit should be sent.

  Sending notifications should obey the following rules in order:
    1. Never send a notification if Findit is not configured to do so.
    2. Never send if the culprit has already been notified by Findit.
    3. Always send if the culprit introduced a new flaky test.
    4. Never send if the culprit is not preceded by a minimum number of
       fully-passing or fully-failing data points.
    5. Never send if there is insufficient confidence that the culprit is indeed
       responsible.

  Any new criteria for deciding when to notify should be implemented within this
  function.

  Args:
    analysis (MasterFlakeAnalysis): The original analysis that identified a
        culprit to be notified.
    action_settings (dict): The action_settings config dict.

  Returns:
    A boolean indicating whether a notification should be sent to the code
        review.

  """
  # Check config.
  should_notify_culprit = action_settings.get(
      'cr_notification_should_notify_flake_culprit')
  if not should_notify_culprit:
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
                     'existing notification')
    return False

  assert analysis.FindMatchingDataPointWithCommitPosition(
      culprit.commit_position)

  # Always notify culprits for newly-added flaky tests.
  if _NewlyAddedTest(analysis, culprit):
    analysis.LogInfo('Sending notification to code review due to adding a new '
                     'flaky test')
    culprit.cr_notification_status = status.RUNNING
    culprit.put()
    return True

  # A series of fully-stable points must precede the culprit.
  if not _HasSeriesOfFullyStablePointsPrecedingCulprit(analysis, culprit):
    analysis.LogInfo('Skipping sending notification to code review due to '
                     'the likelyhood of being a false positive')
    return False

  # Check confidence in culprit.
  if (analysis.confidence_in_culprit < analysis.algorithm_parameters.get(
      'minimum_confidence_to_update_cr',
      flake_constants.DEFAULT_MINIMUM_CONFIDENCE_SCORE_TO_UPDATE_CR)):
    analysis.LogInfo('Skipping sending notification to code review due to '
                     'insufficient confidence')
    return False

  culprit.cr_notification_status = status.RUNNING
  culprit.put()
  return True


def _SendNotificationForCulprit(culprit, review_server_host, change_id):
  """Sends a notification to a code review page.

  Args:
    culprit (FlakeCulprit): The culprit identified to have introduced flakiness.
    review_server_host (str): The code review server host.
    change_id (str): The change id of the culprit.

  Returns:
    Bool indicating whether a notification was successfully sent.
  """
  code_review_settings = FinditConfig().Get().code_review_settings
  codereview = codereview_util.GetCodeReviewForReview(review_server_host,
                                                      code_review_settings)
  sent = False

  if codereview and change_id:
    message = _MESSAGE_TEMPLATE % (culprit.commit_position or culprit.revision,
                                   culprit.key.urlsafe())
    sent = codereview.PostMessage(change_id, message)
  else:
    # Occasionally, a commit was not uploaded for code-review.
    logging.error('No code-review url for %s/%s', culprit.repo_name,
                  culprit.revision)

  suspected_cl_util.UpdateCulpritNotificationStatus(culprit.key.urlsafe(),
                                                    status.COMPLETED
                                                    if sent else status.ERROR)
  return sent


class SendNotificationForFlakeCulpritPipeline(BasePipeline):
  """Pipeline to notify a code review page of introduced flakiness."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, analysis_urlsafe_key):
    """"Sends a notification to a code review page.

    Args:
      analysis_urlsafe_key (str): The urlsafe key of a MasterFlakeAnalysis that
          identified a flake culprit.

    Returns:
      Bool indicating whether or not a notification was sent.
    """
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    if analysis.culprit_urlsafe_key is None:
      analysis.LogInfo(
          'Skipping sending notifications to code review due to no culprit '
          'being identified')
      return False

    action_settings = waterfall_config.GetActionSettings()

    if not _ShouldSendNotification(analysis, action_settings):
      return False

    culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
    assert culprit

    repo_name = culprit.repo_name
    revision = culprit.revision
    culprit_info = suspected_cl_util.GetCulpritInfo(repo_name, revision)

    review_server_host = culprit_info['review_server_host']
    review_change_id = culprit_info['review_change_id']

    return _SendNotificationForCulprit(culprit, review_server_host,
                                       review_change_id)
