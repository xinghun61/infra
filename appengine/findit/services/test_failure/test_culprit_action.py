# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for actions on identified culprits for test failure.

It provides functions to:
  * Determine if Findit should take actions on a culprit.
"""

from datetime import timedelta
import logging

from google.appengine.ext import ndb

from common.waterfall import failure_type
from libs import time_util
from model.wf_suspected_cl import WfSuspectedCL
from services import ci_failure
from waterfall import waterfall_config

_DEFAULT_AUTO_CREATE_REVERT_DAILY_THRESHOLD_TEST = 10
_DEFAULT_AUTO_COMMIT_REVERT_DAILY_THRESHOLD_TEST = 4


def _GetDailyNumberOfRevertedCulprits(limit):
  earliest_time = time_util.GetUTCNow() - timedelta(days=1)
  # TODO(chanli): improve the check for a rare case when two pipelines revert
  # at the same time.
  return WfSuspectedCL.query(
      ndb.AND(WfSuspectedCL.failure_type == failure_type.TEST,
              WfSuspectedCL.revert_created_time >= earliest_time)).count(limit)


def CanAutoCreateRevert(culprit, parameters):
  """Checks if Findit can auto create a revert.

  Args:
    culprit (Basestring): Urlsafe key for the suspected cl.
    parameters (CulpritActionParameters): Parameters to run culprit action
      pipelines.

  Findit can auto create a revert if:
    1. Auto create revert for test is turned on;
    2. The number of reverts in past 24 hours is less than the daily limit;
    3. The culprit is also being suspected by the heuristic analysis.
  """
  heuristic_cls = parameters.heuristic_cls
  if culprit not in heuristic_cls:
    return False

  action_settings = waterfall_config.GetActionSettings()
  # Auto revert has been turned off.
  if not bool(action_settings.get('auto_create_revert_test')):
    return False

  auto_create_revert_daily_threshold_test = action_settings.get(
      'auto_create_revert_daily_threshold_test',
      _DEFAULT_AUTO_CREATE_REVERT_DAILY_THRESHOLD_TEST)
  # Auto revert has exceeded daily limit.
  if _GetDailyNumberOfRevertedCulprits(
      auto_create_revert_daily_threshold_test
  ) >= auto_create_revert_daily_threshold_test:
    logging.info('Auto reverts for test culprits on %s has met daily limit.',
                 time_util.FormatDatetime(time_util.GetUTCNow()))
    return False

  return True


def _GetDailyNumberOfCommits(limit):
  earliest_time = time_util.GetUTCNow() - timedelta(days=1)
  # TODO(chanli): improve the check for a rare case when two pipelines commit
  # at the same time.
  return WfSuspectedCL.query(
      ndb.AND(
          WfSuspectedCL.failure_type == failure_type.TEST,
          WfSuspectedCL.revert_committed_time >= earliest_time)).count(limit)


def CanAutoCommitRevertByFindit():
  """Checks if the revert can be auto committed by Findit.

  The revert can be committed if:
    1. Auto revert and Auto commit is turned on;
    2. The number of commits of reverts in past 24 hours is less than the
      daily limit;
    3. Culprit author has not landed another change yet.
  """
  action_settings = waterfall_config.GetActionSettings()
  if (not bool(action_settings.get('auto_commit_revert_test')) or
      not bool(action_settings.get('auto_create_revert_test'))):
    return False

  auto_commit_revert_daily_threshold_test = action_settings.get(
      'auto_commit_revert_daily_threshold_test',
      _DEFAULT_AUTO_COMMIT_REVERT_DAILY_THRESHOLD_TEST)
  if _GetDailyNumberOfCommits(auto_commit_revert_daily_threshold_test
                             ) >= auto_commit_revert_daily_threshold_test:
    logging.info('Auto commits on %s has met daily limit.',
                 time_util.FormatDatetime(time_util.GetUTCNow()))
    return False
  return True


def GetCulpritsShouldTakeActions(parameters):
  """Checks if the step failure continues in later builds to determine
   should take actions on the culprit or not.

  Returns:
     A set of culprit keys Findit should take action on because the failed steps
     they are responsible for are still failing.
  """
  assert parameters.culprits

  master_name, builder_name, build_number = parameters.build_key.GetParts()
  failure_to_culprit_map = parameters.failure_to_culprit_map
  builds_with_same_steps = ci_failure.GetLaterBuildsWithAnySameStepFailure(
      master_name, builder_name, build_number,
      failure_to_culprit_map.failed_steps)
  if not builds_with_same_steps:
    # Some steps stop to fail, don't need to revert or send notification.
    logging.info(
        'No revert or notification needed for culprit(s) for '
        '%s/%s/%s since the failure has stopped.', master_name, builder_name,
        build_number)
    return []

  culprits_should_take_actions = set(parameters.culprits.keys())

  for step_name, test_culprit_map in failure_to_culprit_map.iteritems():
    step_culprits = set(test_culprit_map.values())
    for build_number, steps in builds_with_same_steps.iteritems():
      if step_name not in steps:
        # Step stops failing, should not take actions on all culprits that are
        # thought to be responsible for failures in this step.
        culprits_should_take_actions = (
            culprits_should_take_actions - step_culprits)
        break
    if not culprits_should_take_actions:
      return []

  return culprits_should_take_actions
