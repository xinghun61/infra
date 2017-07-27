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

_MESSAGE_TEMPLATE = textwrap.dedent("""
Findit (https://goo.gl/kROfz5) identified this CL at revision %s as the culprit
for introducing flakiness in the tests as shown on:
https://findit-for-me.appspot.com/waterfall/flake/flake-culprit?key=%s""")


@ndb.transactional
def _ShouldSendNotification(analysis, action_settings):
  """Returns True if a notification for the culprit should be sent.

  Send notification only when:
    1. Findit is configured to do so.
    2. It was not processed yet.
    3. There is sufficient confidence that the culprit is indeed responsible.

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
    logging.info('Skipping sending notification to code review due to disabled '
                 'or missing parameter set in action_settings')
    return False

  assert analysis.culprit_urlsafe_key
  culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
  assert culprit

  # Check if this culprit has already been notified.
  if culprit.cr_notification_processed:
    logging.info('Skipping sending notification to code review due to existing '
                 'notification')
    return False

  # Check confidence in culprit.
  if (analysis.confidence_in_culprit <
      analysis.algorithm_parameters.get('minimum_confidence_to_update_cr')):
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
      logging.info(('Skipping sending notifications to code review due to no '
                    'culprit being identified for analysis %s/%s/%s/%s/%s'),
                   analysis.master_name, analysis.builder_name,
                   analysis.build_number, analysis.step_name,
                   analysis.test_name)
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
