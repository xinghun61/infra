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

from datetime import timedelta
import logging
import textwrap
import urllib

from google.appengine.ext import ndb

from common import constants
from common import monitoring
from common import rotations
from infra_api_clients.codereview import codereview_util
from libs import analysis_status as status
from libs import time_util
from model.base_suspected_cl import RevertCL
from model.wf_config import FinditConfig
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import buildbot
from waterfall import suspected_cl_util
from waterfall import waterfall_config

CREATED_BY_FINDIT = 0
CREATED_BY_SHERIFF = 1
ERROR = 2
SKIPPED = 3

CULPRIT_IS_A_REVERT = 'Culprit is a revert.'
AUTO_REVERT_OFF = 'Author of the culprit revision has turned off auto-revert.'
REVERTED_BY_SHERIFF = 'Culprit has been reverted by a sheriff or the CL owner.'

_DEFAULT_AUTO_REVERT_DAILY_THRESHOLD = 10
_DEFAULT_AUTO_COMMIT_DAILY_THRESHOLD = 4
_DEFAULT_CULPRIT_COMMIT_LIMIT_HOURS = 24

_MANUAL_LINK = 'https://goo.gl/NPQkv6'
_SURVEY_LINK = 'https://goo.gl/forms/iPQbwFyo98N9tJ7o1'


@ndb.transactional
def _UpdateCulprit(repo_name,
                   revision,
                   revert_status=None,
                   revert_cl=None,
                   skip_revert_reason=None,
                   revert_submission_status=None):
  """Updates culprit entity."""
  culprit = WfSuspectedCL.Get(repo_name, revision)

  culprit.should_be_reverted = True

  culprit.revert_status = revert_status or culprit.revert_status
  culprit.revert_cl = revert_cl or culprit.revert_cl
  culprit.skip_revert_reason = skip_revert_reason or culprit.skip_revert_reason
  culprit.revert_submission_status = (revert_submission_status or
                                      culprit.revert_submission_status)

  if culprit.revert_status != status.RUNNING:
    # Only stores revert_pipeline_id when the revert is ongoing.
    culprit.revert_pipeline_id = None

  if revert_cl:
    culprit.cr_notification_status = status.COMPLETED
    culprit.revert_created_time = time_util.GetUTCNow()
    culprit.cr_notification_time = time_util.GetUTCNow()

  if culprit.revert_submission_status != status.RUNNING:
    culprit.submit_revert_pipeline_id = None

  if culprit.revert_submission_status == status.COMPLETED:
    culprit.revert_committed_time = time_util.GetUTCNow()

  culprit.put()
  return culprit


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
  auto_revert_bug_link = ('https://bugs.chromium.org/p/chromium/issues/entry?%s'
                         ) % (auto_revert_bug_query)

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
        If it is a false positive, please revert and report it
        at %s.

        For more information about Findit auto-revert: %s.

        Sheriffs, it'll be much appreciated if you could take several minutes
        to fill out this survey: %s.""") % (false_positive_bug_link,
                                            _MANUAL_LINK, _SURVEY_LINK)

  # Original CL owner and reviewers are already reviewers when creating the
  # revert, add sheriffs or Findit members to reviewers as well.
  return codereview.AddReviewers(revert_change_id, new_reviewers, message)


###################### Functions to create a revert. ######################


@ndb.transactional
def _CanRevert(repo_name, revision, pipeline_id):
  """Checks if this pipeline can revert.

  This pipeline can revert if:
    No revert of this culprit is complete or skipped;
    No other pipeline is doing the revert on the same culprit.
  """
  culprit = WfSuspectedCL.Get(repo_name, revision)
  assert culprit
  if ((culprit.revert_cl and culprit.revert_status == status.COMPLETED) or
      culprit.revert_status == status.SKIPPED or
      (culprit.revert_status == status.RUNNING and
       culprit.revert_pipeline_id and
       culprit.revert_pipeline_id != pipeline_id)):
    # Revert of the culprit has been created or is being created by another
    # analysis.
    return False

  # Update culprit to ensure only current analysis can revert the culprit.
  culprit.revert_status = status.RUNNING
  culprit.revert_pipeline_id = pipeline_id
  culprit.put()
  return True


def _GetDailyNumberOfRevertedCulprits(limit):
  earliest_time = time_util.GetUTCNow() - timedelta(days=1)
  # TODO (chanli): improve the check for a rare case when two pipelines revert
  # at the same time.
  return WfSuspectedCL.query(
      WfSuspectedCL.revert_created_time >= earliest_time).count(limit)


def ShouldRevert(pipeline_input, pipeline_id):
  """Checks if the culprit should be reverted.

  The culprit should be reverted if:
    1. Auto revert is turned on;
    2. This pipeline can do the revert;
    3. The number of reverts in past 24 hours is less than the daily limit.
  """
  action_settings = waterfall_config.GetActionSettings()
  # Auto revert has been turned off.
  if not bool(action_settings.get('auto_create_revert_compile')):
    return False

  if not _CanRevert(pipeline_input.cl_key.repo_name,
                    pipeline_input.cl_key.revision, pipeline_id):
    # Either revert is done, skipped or handled by another pipeline.
    return False

  auto_revert_daily_threshold = action_settings.get(
      'auto_revert_daily_threshold', _DEFAULT_AUTO_REVERT_DAILY_THRESHOLD)
  # Auto revert has exceeded daily limit.
  if _GetDailyNumberOfRevertedCulprits(
      auto_revert_daily_threshold) >= auto_revert_daily_threshold:
    logging.info('Auto reverts on %s has met daily limit.',
                 time_util.FormatDatetime(time_util.GetUTCNow()))
    return False

  return True


def _IsOwnerFindit(owner_email):
  return owner_email == constants.DEFAULT_SERVICE_ACCOUNT


def _IsCulpritARevert(cl_info):
  return bool(cl_info.revert_of)


def RevertCulprit(pipeline_input):
  """Creates a revert of a culprit and adds reviewers.

  Args:
    pipeline_input (CreateRevertCLPipelineInput): Information needed to
      create a revert.

  Returns:
    Status of this reverting.
  """
  repo_name = pipeline_input.cl_key.repo_name
  revision = pipeline_input.cl_key.revision
  build_id = pipeline_input.build_id

  culprit = _UpdateCulprit(repo_name, revision)
  # 0. Gets information about this culprit.
  culprit_info = suspected_cl_util.GetCulpritInfo(repo_name, revision)

  culprit_commit_position = culprit_info['commit_position']
  culprit_change_id = culprit_info['review_change_id']
  culprit_host = culprit_info['review_server_host']

  codereview = codereview_util.GetCodeReviewForReview(culprit_host)

  if not codereview or not culprit_change_id:  # pragma: no cover
    logging.error('Failed to get change id for %s/%s' % (repo_name, revision))
    _UpdateCulprit(repo_name, revision, revert_status=status.ERROR)
    return ERROR

  culprit_cl_info = codereview.GetClDetails(culprit_change_id)
  if not culprit_cl_info:  # pragma: no cover
    logging.error('Failed to get cl_info for %s/%s' % (repo_name, revision))
    _UpdateCulprit(repo_name, revision, revert_status=status.ERROR)
    return ERROR

  # Checks if the culprit is a revert. If yes, bail out.
  if _IsCulpritARevert(culprit_cl_info):
    _UpdateCulprit(
        repo_name,
        revision,
        status.SKIPPED,
        skip_revert_reason=CULPRIT_IS_A_REVERT)
    return SKIPPED

  if culprit_cl_info.auto_revert_off:
    _UpdateCulprit(
        repo_name, revision, status.SKIPPED, skip_revert_reason=AUTO_REVERT_OFF)
    return SKIPPED

  # 1. Checks if a revert CL by sheriff has been created.
  reverts = culprit_cl_info.GetRevertCLsByRevision(revision)

  if reverts is None:  # pragma: no cover
    # if no reverts, reverts should be [], only when some error happens it will
    # be None.
    logging.error('Failed to find patchset_id for %s/%s' % (repo_name,
                                                            revision))
    _UpdateCulprit(repo_name, revision, revert_status=status.ERROR)
    return ERROR

  findit_revert = None
  for revert in reverts:
    if _IsOwnerFindit(revert.reverting_user_email):
      findit_revert = revert
      break

  if reverts and not findit_revert:
    # Sheriff(s) created the revert CL(s).
    _UpdateCulprit(
        repo_name,
        revision,
        revert_status=status.SKIPPED,
        skip_revert_reason=REVERTED_BY_SHERIFF)
    return CREATED_BY_SHERIFF

  revert_change_id = None
  if findit_revert:
    revert_change_id = findit_revert.reverting_cl.change_id

  # 2. Crreate revert CL.
  # TODO (chanli): Better handle cases where 2 analyses are trying to revert
  # at the same time.
  if not revert_change_id:
    sample_build = build_id.split('/')
    sample_build_url = buildbot.CreateBuildUrl(*sample_build)
    revert_reason = textwrap.dedent("""
        Findit (https://goo.gl/kROfz5) identified CL at revision %s as the
        culprit for failures in the build cycles as shown on:
        https://findit-for-me.appspot.com/waterfall/culprit?key=%s\n
        Sample Failed Build: %s""") % (culprit_commit_position or revision,
                                       culprit.key.urlsafe(), sample_build_url)

    revert_change_id = codereview.CreateRevert(
        revert_reason, culprit_change_id,
        culprit_cl_info.GetPatchsetIdByRevision(revision))

    if not revert_change_id:  # pragma: no cover
      _UpdateCulprit(repo_name, revision, status.ERROR)
      logging.error('Revert for culprit %s/%s failed.' % (repo_name, revision))
      return ERROR

  # Save revert CL info and notification info to culprit.
  if not culprit.revert_cl:
    revert_cl = RevertCL()
    revert_cl.revert_cl_url = codereview.GetCodeReviewUrl(revert_change_id)
    revert_cl.created_time = time_util.GetUTCNow()
    _UpdateCulprit(repo_name, revision, None, revert_cl=revert_cl)

  # 3. Add reviewers.
  # If Findit cannot commit the revert, add sheriffs as reviewers and ask them
  # to 'LGTM' and commit the revert.
  if not waterfall_config.GetActionSettings().get('auto_commit_revert_compile'):
    success = _AddReviewers(revision,
                            culprit.key.urlsafe(), codereview, revert_change_id,
                            False)
    if not success:  # pragma: no cover
      _UpdateCulprit(repo_name, revision, status.ERROR)
      logging.error('Failed to add reviewers for revert of'
                    ' culprit %s/%s' % (repo_name, revision))
      return ERROR
  _UpdateCulprit(repo_name, revision, revert_status=status.COMPLETED)
  return CREATED_BY_FINDIT


###################### Functions to commit a revert. ######################


@ndb.transactional
def _CanCommitRevert(repo_name, revision, pipeline_id):
  """Checks if current pipeline should do the auto commit.

  This pipeline should commit a revert of the culprit if:
    1. There is a revert for the culprit;
    2. The revert have copleted;
    3. The revert should be auto commited;
    4. No other pipeline is committing the revert;
    5. No other pipeline is supposed to handle the auto commit.
  """
  culprit = WfSuspectedCL.Get(repo_name, revision)
  assert culprit

  if (not culprit.revert_cl or
      culprit.revert_submission_status == status.COMPLETED or
      culprit.revert_status != status.COMPLETED or
      culprit.revert_submission_status == status.SKIPPED or
      (culprit.revert_submission_status == status.RUNNING and
       culprit.submit_revert_pipeline_id and
       culprit.submit_revert_pipeline_id != pipeline_id)):
    return False

  # Update culprit to ensure only current analysis can commit the revert.
  culprit.revert_submission_status = status.RUNNING
  culprit.submit_revert_pipeline_id = pipeline_id
  culprit.put()
  return True


def _GetDailyNumberOfCommits(limit):
  earliest_time = time_util.GetUTCNow() - timedelta(days=1)
  # TODO (chanli): improve the check for a rare case when two pipelines commit
  # at the same time.
  return WfSuspectedCL.query(
      WfSuspectedCL.revert_committed_time >= earliest_time).count(limit)


def _CulpritWasAutoCommitted(culprit_info):
  author_email = culprit_info['author']['email']
  return author_email in constants.AUTO_COMMIT_ACCOUNTS


def _ShouldCommitRevert(repo_name, revision, revert_status, pipeline_id):
  """Checks if the revert should be auto committed.

  The revert should be committed if:
    1. Auto revert and Auto commit is turned on;
    2. The revert is created by Findit;
    3. This pipeline can commit the revert;
    4. The number of commits of reverts in past 24 hours is less than the
      daily limit;
    5. The revert is done in Gerrit;
    6. The culprit is committed within threshold.
  """
  action_settings = waterfall_config.GetActionSettings()
  if (not revert_status == CREATED_BY_FINDIT or
      not bool(action_settings.get('auto_commit_revert_compile')) or
      not bool(action_settings.get('auto_create_revert_compile'))):
    return False

  if not _CanCommitRevert(repo_name, revision, pipeline_id):
    return False

  auto_commit_daily_threshold = action_settings.get(
      'auto_commit_daily_threshold', _DEFAULT_AUTO_COMMIT_DAILY_THRESHOLD)
  if _GetDailyNumberOfCommits(
      auto_commit_daily_threshold) >= auto_commit_daily_threshold:
    logging.info('Auto commits on %s has met daily limit.',
                 time_util.FormatDatetime(time_util.GetUTCNow()))
    return False

  culprit_commit_limit_hours = action_settings.get(
      'culprit_commit_limit_hours', _DEFAULT_CULPRIT_COMMIT_LIMIT_HOURS)

  # Gets Culprit information.
  culprit = WfSuspectedCL.Get(repo_name, revision)
  assert culprit

  culprit_info = suspected_cl_util.GetCulpritInfo(repo_name, revision)

  # Checks if the culprit is an DEPS autoroll by checking the author's email.
  # If it is, bail out of auto commit for now.
  if _CulpritWasAutoCommitted(culprit_info):
    return False

  culprit_change_id = culprit_info['review_change_id']
  culprit_host = culprit_info['review_server_host']
  # Makes sure codereview is Gerrit, as only Gerrit is supported at the moment.
  if not codereview_util.IsCodeReviewGerrit(culprit_host):
    _UpdateCulprit(repo_name, revision, revert_submission_status=status.SKIPPED)
    return False
  # Makes sure the culprit landed less than x hours ago (default: 24 hours).
  # Bail otherwise.
  codereview = codereview_util.GetCodeReviewForReview(culprit_host)
  culprit_cl_info = codereview.GetClDetails(culprit_change_id)
  culprit_commit = culprit_cl_info.GetCommitInfoByRevision(revision)
  culprit_commit_time = culprit_commit.timestamp

  if time_util.GetUTCNow() - culprit_commit_time > timedelta(
      hours=culprit_commit_limit_hours):
    logging.info('Culprit %s/%s was committed over %d hours ago, stop auto '
                 'commit.' % (repo_name, revision, culprit_commit_limit_hours))
    _UpdateCulprit(repo_name, revision, revert_submission_status=status.SKIPPED)
    return False

  return True


def CommitRevert(pipeline_input, pipeline_id):
  # Note that we don't know which was the final action taken by the pipeline
  # before this point. That is why this is where we increment the appropriate
  # metrics.
  repo_name = pipeline_input.cl_key.repo_name
  revision = pipeline_input.cl_key.revision
  revert_status = pipeline_input.revert_status
  if not _ShouldCommitRevert(repo_name, revision, revert_status, pipeline_id):
    if revert_status == CREATED_BY_FINDIT:
      monitoring.culprit_found.increment({
          'type': 'compile',
          'action_taken': 'revert_created'
      })
    elif revert_status == CREATED_BY_SHERIFF:
      monitoring.culprit_found.increment({
          'type': 'compile',
          'action_taken': 'revert_confirmed'
      })
    else:
      monitoring.culprit_found.increment({
          'type': 'compile',
          'action_taken': 'revert_status_error'
      })
    return False

  culprit_info = suspected_cl_util.GetCulpritInfo(repo_name, revision)
  culprit_host = culprit_info['review_server_host']
  codereview = codereview_util.GetCodeReviewForReview(culprit_host)

  culprit = WfSuspectedCL.Get(repo_name, revision)
  revert_change_id = codereview.GetChangeIdFromReviewUrl(culprit.revert_cl_url)

  committed = codereview.SubmitRevert(revert_change_id)

  if committed:
    _AddReviewers(revision,
                  culprit.key.urlsafe(), codereview, revert_change_id, True)
    _UpdateCulprit(
        repo_name, revision, revert_submission_status=status.COMPLETED)
    monitoring.culprit_found.increment({
        'type': 'compile',
        'action_taken': 'revert_committed'
    })
  else:
    _AddReviewers(revision,
                  culprit.key.urlsafe(), codereview, revert_change_id, False)
    _UpdateCulprit(repo_name, revision, revert_submission_status=status.ERROR)
    monitoring.culprit_found.increment({
        'type': 'compile',
        'action_taken': 'commit_error'
    })
  return committed


###################### Functions to send notification. ######################
@ndb.transactional
def _ShouldSendNotification(repo_name, revision, force_notify, revert_status):
  """Returns True if a notification for the culprit should be sent.

  Send notification only when:
    1. The culprit is not reverted.
    2. It was not processed yet.
    3. The culprit is for multiple failures in different builds to avoid false
      positive due to flakiness.

  Any new criteria for deciding when to notify should be implemented within this
  function.

  Args:
    repo_name, revision (str): Uniquely identify the revision to notify about.
    force_notify (bool): If we should skip the fail number threshold check.
    revert_status (int): Status of revert if exists.

  Returns:
    A boolean indicating whether we should send the notification.

  """
  if revert_status == CREATED_BY_FINDIT:
    # Already notified when revert, bail out.
    return False

  if revert_status == CREATED_BY_SHERIFF:
    force_notify = True

  # TODO (chanli): Add check for if confidence for the culprit is
  # over threshold.
  culprit = WfSuspectedCL.Get(repo_name, revision)
  assert culprit

  if culprit.cr_notification_processed:
    return False

  action_settings = waterfall_config.GetActionSettings()
  # Set some impossible default values to prevent notification by default.
  build_num_threshold = action_settings.get('cr_notification_build_threshold',
                                            100000)
  if force_notify or len(culprit.builds) >= build_num_threshold:
    culprit.cr_notification_status = status.RUNNING
    culprit.put()
    return True
  return False


def SendNotificationForCulprit(pipeline_input):
  repo_name = pipeline_input.cl_key.repo_name
  revision = pipeline_input.cl_key.revision
  force_notify = pipeline_input.force_notify
  revert_status = pipeline_input.revert_status

  if not _ShouldSendNotification(repo_name, revision, force_notify,
                                 revert_status):
    return False

  culprit_info = suspected_cl_util.GetCulpritInfo(repo_name, revision)
  commit_position = culprit_info['commit_position']
  review_server_host = culprit_info['review_server_host']
  review_change_id = culprit_info['review_change_id']

  code_review_settings = FinditConfig().Get().code_review_settings
  codereview = codereview_util.GetCodeReviewForReview(review_server_host,
                                                      code_review_settings)
  culprit = WfSuspectedCL.Get(repo_name, revision)

  sent = False
  if codereview and review_change_id:
    # Occasionally, a commit was not uploaded for code-review.
    action = 'identified'
    should_email = True
    if revert_status == CREATED_BY_SHERIFF:
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

  suspected_cl_util.UpdateCulpritNotificationStatus(culprit.key.urlsafe(),
                                                    status.COMPLETED
                                                    if sent else status.ERROR)
  return sent
