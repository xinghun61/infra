# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for actions on identified culprits for build failure.

It provides functions to:
  * Determine if Findit should take actions on a culprit
"""

import logging

from google.appengine.ext import ndb

from common.waterfall import failure_type
from libs import analysis_status
from model import entity_util
from model.wf_suspected_cl import WfSuspectedCL
from services import ci_failure
from services import gerrit
from services import irc
from services import monitoring
from waterfall import waterfall_config


# Functions to add metrics.
def MonitorRevertAction(build_failure_type, revert_status, commit_status):
  build_failure_type = failure_type.GetDescriptionForFailureType(
      build_failure_type)
  if revert_status == gerrit.CREATED_BY_FINDIT:
    if commit_status == gerrit.COMMITTED:
      monitoring.OnCulpritAction(build_failure_type, 'revert_committed')
    elif commit_status == gerrit.ERROR:
      monitoring.OnCulpritAction(build_failure_type, 'revert_commit_error')
    else:
      monitoring.OnCulpritAction(build_failure_type, 'revert_created')
  elif revert_status == gerrit.CREATED_BY_SHERIFF:
    monitoring.OnCulpritAction(build_failure_type, 'revert_confirmed')
  elif revert_status == gerrit.ERROR:
    monitoring.OnCulpritAction(build_failure_type, 'revert_status_error')


def MonitoringCulpritNotification(build_failure_type, action_type, sent):
  build_failure_type = failure_type.GetDescriptionForFailureType(
      build_failure_type)
  if sent:
    monitoring.OnCulpritAction(build_failure_type, '%s_notified' % action_type)
  else:
    monitoring.OnCulpritAction(build_failure_type,
                               '%s_notified_error' % action_type)


def ShouldTakeActionsOnCulprit(parameters):
  master_name, builder_name, build_number = parameters.build_key.GetParts()

  assert parameters.culprits

  if ci_failure.AnyNewBuildSucceeded(master_name, builder_name, build_number):
    # The builder has turned green, don't need to revert or send notification.
    logging.info('No revert or notification needed for culprit(s) for '
                 '%s/%s/%s since the builder has turned green.', master_name,
                 builder_name, build_number)
    return False

  return True


# Functions to create a revert.
@ndb.transactional
def _CanCreateRevertForCulprit(parameters, analysis_id):
  """Checks if a culprit can be reverted by a specific analysis.

  The culprit can be reverted by the analysis if:
    No revert of this culprit is complete or skipped, and
    no other pipeline is doing the revert on the same culprit.
  """
  culprit = entity_util.GetEntityFromUrlsafeKey(parameters.cl_key)
  assert culprit

  if ((culprit.revert_cl and culprit.revert_status == analysis_status.COMPLETED)
      or culprit.revert_status == analysis_status.SKIPPED or
      (culprit.revert_status == analysis_status.RUNNING and
       culprit.revert_pipeline_id and
       culprit.revert_pipeline_id != analysis_id)):
    # Revert of the culprit has been created or is being created by another
    # analysis.
    return False

  # Update culprit to ensure only current analysis can revert the culprit.
  culprit.revert_status = analysis_status.RUNNING
  culprit.revert_pipeline_id = analysis_id
  culprit.put()
  return True


def GetSampleFailedStepName(repo_name, revision, build_id):
  culprit = WfSuspectedCL.Get(repo_name, revision)

  if culprit and culprit.builds:
    if (culprit.builds.get(build_id) and
        culprit.builds[build_id].get('failures')):
      failures = culprit.builds[build_id]['failures']
    else:
      logging.warning('%s is not found in culprit %s/%s\'s build,'
                      ' using another build to get a sample failed step.',
                      build_id, repo_name, revision)
      failures = culprit.builds.values()[0]['failures']
    return failures.keys()[0]
  logging.error('Cannot get a sample failed step for culprit %s/%s.', repo_name,
                revision)
  return ''


def RevertCulprit(parameters, analysis_id):
  culprit = entity_util.GetEntityFromUrlsafeKey(parameters.cl_key)
  assert culprit

  repo_name = culprit.repo_name
  revision = culprit.revision
  build_id = parameters.build_id

  if _CanCreateRevertForCulprit(parameters, analysis_id):
    return gerrit.RevertCulprit(
        repo_name, revision, build_id, parameters.failure_type,
        GetSampleFailedStepName(repo_name, revision, build_id))
  return gerrit.SKIPPED


# Functions to commit the auto_created revert.
@ndb.transactional
def _CanCommitRevert(parameters, pipeline_id):
  """Checks if an auto-created revert of a culprit can be committed.

  The revert of the culprit can be committed by the analysis if all below are
  True:
    0. Findit reverts the culprit;
    1. There is a revert for the culprit;
    2. The revert has completed;
    3. The revert should be auto commited;
    4. No other pipeline is committing the revert;
    5. No other pipeline is supposed to handle the auto commit.
  """
  if not parameters.revert_status == gerrit.CREATED_BY_FINDIT:
    return False

  culprit = entity_util.GetEntityFromUrlsafeKey(parameters.cl_key)
  assert culprit

  if (not culprit.revert_cl or
      culprit.revert_submission_status == analysis_status.COMPLETED or
      culprit.revert_status != analysis_status.COMPLETED or
      culprit.revert_submission_status == analysis_status.SKIPPED or
      (culprit.revert_submission_status == analysis_status.RUNNING and
       culprit.submit_revert_pipeline_id and
       culprit.submit_revert_pipeline_id != pipeline_id)):
    return False

  # Update culprit to ensure only current analysis can commit the revert.
  culprit.revert_submission_status = analysis_status.RUNNING
  culprit.submit_revert_pipeline_id = pipeline_id
  culprit.put()
  return True


def CommitRevert(parameters, analysis_id):
  commit_status = gerrit.SKIPPED
  if _CanCommitRevert(parameters, analysis_id):
    commit_status = gerrit.CommitRevert(parameters)

  MonitorRevertAction(parameters.failure_type, parameters.revert_status,
                      commit_status)
  return commit_status


# Functions to send notification to irc.
def SendMessageToIRC(parameters):
  """Sends a message to irc if Findit auto-reverts a culprit."""
  revert_status = parameters.revert_status
  commit_status = parameters.commit_status
  sent = False

  if revert_status == gerrit.CREATED_BY_FINDIT:
    culprit = entity_util.GetEntityFromUrlsafeKey(parameters.cl_key)

    if not culprit:
      logging.error('Failed to send notification to irc about culprit:'
                    ' entity not found in datastore.')
    else:
      repo_name = culprit.repo_name
      revision = culprit.revision
      revert_cl_url = culprit.revert_cl_url
      if not revert_cl_url:
        logging.error('Failed to send notification to irc about culprit %s, %s:'
                      ' revert CL url not found.' % (repo_name, revision))
      else:
        sent = irc.SendMessageToIrc(revert_cl_url,
                                    culprit.commit_position, revision,
                                    culprit.key.urlsafe(), commit_status)

  MonitoringCulpritNotification(parameters.failure_type, 'irc', sent)
  return sent


# Functions to send notification to culprit.
def ShouldForceNotify(culprit, parameter):
  """Checks if Findit should force to notify a culprit.

  Criteria to force notify:
    * The culprit is also a suspect.
  """
  heuristic_cls = parameter.heuristic_cls
  return culprit in heuristic_cls


@ndb.transactional
def _ShouldSendNotification(repo_name, revision, force_notify, revert_status,
                            build_num_threshold):
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
    build_num_threshold (int): Threshold for the number of builds the culprit is
      responsible for. A notification should be sent when number of builds
      exceeds the threshold.

  Returns:
    A boolean indicating whether we should send the notification.

  """
  if revert_status == gerrit.CREATED_BY_FINDIT:
    # Already notified when revert, bail out.
    return False

  if revert_status == gerrit.CREATED_BY_SHERIFF:
    force_notify = True

  # TODO (chanli): Add check for if confidence for the culprit is
  # over threshold.
  culprit = WfSuspectedCL.Get(repo_name, revision)
  assert culprit

  if culprit.cr_notification_processed:
    return False

  if force_notify or len(culprit.builds) >= build_num_threshold:
    culprit.cr_notification_status = analysis_status.RUNNING
    culprit.put()
    return True
  return False


def SendNotificationForCulprit(parameters):
  culprit = entity_util.GetEntityFromUrlsafeKey(parameters.cl_key)
  assert culprit

  revision = culprit.revision
  repo_name = culprit.repo_name

  force_notify = parameters.force_notify
  revert_status = parameters.revert_status
  sent = False

  action_settings = waterfall_config.GetActionSettings()
  # Set some impossible default values to prevent notification by default.
  build_num_threshold = action_settings.get('cr_notification_build_threshold',
                                            100000)
  if _ShouldSendNotification(repo_name, revision, force_notify, revert_status,
                             build_num_threshold):
    sent = gerrit.SendNotificationForCulprit(repo_name, revision, revert_status)

  MonitoringCulpritNotification(parameters.failure_type, 'culprit', sent)
  return sent
