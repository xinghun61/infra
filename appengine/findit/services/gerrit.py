# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for gerrit_related operations.

It provides fuctions to:
  * Use rules to check if a CL can be auto reverted
  * Auto create a revert CL
  * Use rules to check if a revert can be auto submitted
  * Auto submit reverts that are created by Findit
  * Send notifications to codereview
"""

import logging
import textwrap
import urllib

from google.appengine.ext import ndb

from common import constants
from common import rotations
from common.waterfall import failure_type
from infra_api_clients.codereview import codereview_util
from libs import analysis_status as status
from libs import time_util
from model import entity_util
from model.base_suspected_cl import RevertCL
from model.flake.flake_culprit import FlakeCulprit
from services import constants as services_constants
from services import git
from waterfall import buildbot
from waterfall import suspected_cl_util
from waterfall import waterfall_config

DEFAULT_AUTO_CREATE_REVERT_DAILY_THRESHOLD_COMPILE = 10
DEFAULT_AUTO_COMMIT_REVERT_DAILY_THRESHOLD_COMPILE = 4

_MANUAL_LINK = 'https://goo.gl/adB34D'
_SURVEY_LINK = 'https://goo.gl/forms/iPQbwFyo98N9tJ7o1'


def _GetCodeReview(code_review_data):
  """Get codereview object based on review_server_host in code_review_data."""
  if not code_review_data or not code_review_data.get('review_server_host'):
    return None
  return codereview_util.GetCodeReviewForReview(
      code_review_data['review_server_host'])


def _AddReviewers(revision, culprit_key, codereview, revert_change_id,
                  submitted):
  """Adds sheriffs to reviewers and sends messages.

  Based on the status of the revert - submitted or not, sends different messages
  to reviewers.

  Args:
    culprit_key (str): url-safe key for the culprit.
    revert_change_id (str): Id of the revert change.
    submitted (bool): If the revert is submitted or not.
  """
  culprit_link = ('https://findit-for-me.appspot.com/waterfall/culprit?key=%s' %
                  culprit_key)
  false_positive_bug_query = urllib.urlencode({
      'status': 'Available',
      'labels': 'Test-Findit-Wrong',
      'components': 'Tools>Test>FindIt',
      'summary': 'Wrongly blame %s' % revision,
      'comment': 'Detail is %s' % culprit_link
  })
  false_positive_bug_link = (
      'https://bugs.chromium.org/p/chromium/issues/entry?%s') % (
          false_positive_bug_query)

  auto_revert_bug_query = urllib.urlencode({
      'status': 'Available',
      'components': 'Tools>Test>FindIt>Autorevert',
      'summary': 'Auto Revert failed on %s' % revision,
      'comment': 'Detail is %s' % culprit_link
  })
  auto_revert_bug_link = (
      'https://bugs.chromium.org/p/chromium/issues/entry?%s') % (
          auto_revert_bug_query)

  new_reviewers = rotations.current_sheriffs()

  if not submitted:
    # Findit only creates the revert but doesn't intend to submit it.
    # This should only be used when auto_commit is disabled.
    message = textwrap.dedent("""
        Sheriffs, CL owner or CL reviewers:
        Please submit this revert if it is correct.
        If it is a false positive, please abandon and report it
        at %s.
        If failed to submit the revert, please abandon it and report the failure
        at %s.

        For more information about Findit auto-revert: %s.

        Sheriffs, it'll be much appreciated if you could take several minutes
        to fill out this survey: %s.""") % (false_positive_bug_link,
                                            auto_revert_bug_link, _MANUAL_LINK,
                                            _SURVEY_LINK)
  else:
    # Findit submits the revert successfully. Add sheriffs to confirm the
    # revert is correct.
    message = textwrap.dedent("""
        Sheriffs, CL owner or CL reviewers:
        Please confirm this revert if it is correct.
        If it is a false positive, please reland the original CL and report this
        false positive at %s.

        For more information about Findit auto-revert: %s.

        Sheriffs, it'll be much appreciated if you could take several minutes
        to fill out this survey: %s.""") % (false_positive_bug_link,
                                            _MANUAL_LINK, _SURVEY_LINK)

  # Original CL owner and reviewers are already reviewers when creating the
  # revert, add sheriffs or Findit members to reviewers as well.
  return codereview.AddReviewers(revert_change_id, new_reviewers, message)


###################### Functions to create a revert. ######################
def _IsOwnerFindit(owner_email):
  return owner_email == constants.DEFAULT_SERVICE_ACCOUNT


def _IsCulpritARevert(cl_info):
  return bool(cl_info.revert_of)


def _GenerateRevertReasonForFailure(build_id, commit_position, revision,
                                    culprit, sample_step_name):
  sample_build = build_id.split('/')
  sample_build_url = buildbot.CreateBuildUrl(*sample_build)
  return textwrap.dedent("""
      Findit (https://goo.gl/kROfz5) identified CL at revision %s as the
      culprit for failures in the build cycles as shown on:
      https://findit-for-me.appspot.com/waterfall/culprit?key=%s\n
      Sample Failed Build: %s\n
      Sample Failed Step: %s""") % (commit_position or revision,
                                    culprit.key.urlsafe(), sample_build_url,
                                    sample_step_name)


def _GenerateRevertReasonForFlake(build_id, commit_position, revision, culprit):
  analysis = ndb.Key(urlsafe=culprit.flake_analysis_urlsafe_keys[-1]).get()
  assert analysis

  sample_build = build_id.split('/')
  sample_build_url = buildbot.CreateBuildUrl(*sample_build)
  return textwrap.dedent("""
      Findit (https://goo.gl/kROfz5) identified CL at revision %s as the
      culprit for flakes in the build cycles as shown on:
      https://findit-for-me.appspot.com/waterfall/flake/flake-culprit?key=%s\n
      Sample Failed Build: %s\n
      Sample Failed Step: %s\n
      Sample Flaky Test: %s""") % (
      commit_position or revision,
      culprit.key.urlsafe(),
      sample_build_url,
      analysis.original_step_name,
      analysis.original_test_name,
  )


def _GetBugIdForCulprit(culprit):
  if not isinstance(culprit, FlakeCulprit):
    return None

  analysis = ndb.Key(urlsafe=culprit.flake_analysis_urlsafe_keys[-1]).get()
  assert analysis

  return analysis.bug_id


def RevertCulprit(urlsafe_key, build_id, build_failure_type, sample_step_name,
                  codereview_info):
  """Creates a revert of a culprit and adds reviewers.

  Args:
    urlsafe_key (str): Key to the ndb model.
    build_id (str): Id of the sample failed build.
    build_failure_type (int): Failure type: compile, test or flake.
    sample_step_name (str): Sample failed step in the failed build.
    codereview_info (dict): Code review information about the culprit.

  Returns:
    (int, string, string):
      - Status of the reverting;
      - change_id of the revert;
      - reason why revert is skipped if it is skipped.
  """

  culprit = entity_util.GetEntityFromUrlsafeKey(urlsafe_key)
  repo_name = culprit.repo_name
  revision = culprit.revision
  # 0. Gets information about this culprit.
  culprit_commit_position = codereview_info['commit_position']
  culprit_change_id = codereview_info['review_change_id']

  codereview = _GetCodeReview(codereview_info)

  if not codereview or not culprit_change_id:  # pragma: no cover
    logging.error('Failed to get change id for %s/%s', repo_name, revision)
    return services_constants.ERROR, None, None

  culprit_cl_info = codereview.GetClDetails(culprit_change_id)
  if not culprit_cl_info:  # pragma: no cover
    logging.error('Failed to get cl_info for %s/%s', repo_name, revision)
    return services_constants.ERROR, None, None

  # Checks if the culprit is a revert. If yes, bail out.
  if _IsCulpritARevert(culprit_cl_info):
    return (services_constants.SKIPPED, None,
            services_constants.CULPRIT_IS_A_REVERT)

  if culprit_cl_info.auto_revert_off:
    return services_constants.SKIPPED, None, services_constants.AUTO_REVERT_OFF

  # 1. Checks if a revert CL by sheriff has been created.
  reverts = culprit_cl_info.GetRevertCLsByRevision(revision)

  if reverts is None:  # pragma: no cover
    # if no reverts, reverts should be [], only when some error happens it will
    # be None.
    logging.error(
        'Failed to find patchset_id for %s/%s' % (repo_name, revision))
    return services_constants.ERROR, None, None

  findit_revert = None
  for revert in reverts:
    if _IsOwnerFindit(revert.reverting_user_email):
      findit_revert = revert
      break

  if reverts and not findit_revert:
    # Sheriff(s) created the revert CL(s).
    return (services_constants.CREATED_BY_SHERIFF, None,
            services_constants.REVERTED_BY_SHERIFF)

  revert_change_id = None
  if findit_revert:
    revert_change_id = findit_revert.reverting_cl.change_id

  # 2. Crreate revert CL.
  # TODO (chanli): Better handle cases where 2 analyses are trying to revert
  # at the same time.
  if not revert_change_id:
    if isinstance(culprit, FlakeCulprit):
      revert_reason = _GenerateRevertReasonForFlake(
          build_id, culprit_commit_position, revision, culprit)
    else:
      revert_reason = _GenerateRevertReasonForFailure(
          build_id, culprit_commit_position, revision, culprit,
          sample_step_name)
    bug_id = _GetBugIdForCulprit(culprit)
    revert_change_id = codereview.CreateRevert(
        revert_reason,
        culprit_change_id,
        culprit_cl_info.GetPatchsetIdByRevision(revision),
        bug_id=bug_id)

    if not revert_change_id:  # pragma: no cover
      return services_constants.ERROR, None, None

  # Save revert CL info and notification info to culprit.
  revert_cl = None
  if not culprit.revert_cl:
    revert_cl = RevertCL()
    revert_cl.revert_cl_url = codereview.GetCodeReviewUrl(revert_change_id)
    revert_cl.created_time = time_util.GetUTCNow()

  # 3. Add reviewers.
  # If Findit cannot commit the revert, add sheriffs as reviewers and ask them
  # to 'LGTM' and commit the revert.
  action_settings = waterfall_config.GetActionSettings()
  can_commit_revert = (
      action_settings.get('auto_commit_revert_compile')
      if build_failure_type == failure_type.COMPILE else
      action_settings.get('auto_commit_revert_test'))
  if not can_commit_revert:
    success = _AddReviewers(revision, culprit.key.urlsafe(), codereview,
                            revert_change_id, False)
    if not success:  # pragma: no cover
      logging.error('Failed to add reviewers for revert of'
                    ' culprit %s/%s' % (repo_name, revision))
      return services_constants.ERROR, revert_cl, None
  return services_constants.CREATED_BY_FINDIT, revert_cl, None


###################### Functions to commit a revert. ######################


def CommitRevert(parameters, codereview_info):
  """Commits a revert.

  Args:
    parameters(SubmitRevertCLParameters): parameters needed to commit a revert.
    codereview_info(dict_: Code review information for the change that will be
      reverted.
  """
  # Note that we don't know which was the final action taken by the pipeline
  # before this point. That is why this is where we increment the appropriate
  # metrics.
  culprit = entity_util.GetEntityFromUrlsafeKey(parameters.cl_key)
  assert culprit

  revision = culprit.revision

  codereview = _GetCodeReview(codereview_info)
  if not codereview:
    logging.error('Failed to get codereview object for change %s/%s.',
                  culprit.repo_name, revision)
    return services_constants.ERROR

  if not codereview_util.IsCodeReviewGerrit(
      codereview_info['review_server_host']):
    return services_constants.SKIPPED

  revert_change_id = codereview.GetChangeIdFromReviewUrl(culprit.revert_cl_url)

  committed = codereview.SubmitRevert(revert_change_id)

  if committed:
    _AddReviewers(revision, culprit.key.urlsafe(), codereview, revert_change_id,
                  True)
  else:
    _AddReviewers(revision, culprit.key.urlsafe(), codereview, revert_change_id,
                  False)
  return services_constants.COMMITTED if committed else services_constants.ERROR


###################### Functions to send notification. ######################
def SendNotificationForCulprit(parameters, codereview_info):
  """Sends notification for a change on Gerrit.

  Args:
    parameters(SendNotificationForCulpritParameters): parameters needed to send
      notificaiton to a change.
    codereview_info(dict_: Code review information for the culprit change.
  """
  culprit = entity_util.GetEntityFromUrlsafeKey(parameters.cl_key)
  assert culprit

  revision = culprit.revision
  repo_name = culprit.repo_name

  codereview = _GetCodeReview(codereview_info)
  if not codereview:
    logging.error('Failed to get codereview object for change %s/%s.',
                  repo_name, revision)
    return False

  commit_position = codereview_info['commit_position']
  review_change_id = codereview_info['review_change_id']

  sent = False
  if codereview and review_change_id:
    # Occasionally, a commit was not uploaded for code-review.
    action = 'identified'
    should_email = True
    if parameters.revert_status == services_constants.CREATED_BY_SHERIFF:
      action = 'confirmed'
      should_email = False

    message = textwrap.dedent("""
    Findit (https://goo.gl/kROfz5) %s this CL at revision %s as the culprit for
    failures in the build cycles as shown on:
    https://findit-for-me.appspot.com/waterfall/culprit?key=%s""") % (
        action, commit_position or revision, culprit.key.urlsafe())
    sent = codereview.PostMessage(review_change_id, message, should_email)
  else:
    logging.error('No code-review url for %s/%s', repo_name, revision)

  suspected_cl_util.UpdateCulpritNotificationStatus(
      culprit.key.urlsafe(), status.COMPLETED if sent else status.ERROR)
  return sent
