# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module is for actions on identified culprits for compile failure.

It provides functions to:
  * Determine if Findit should take actions on a culprit
"""

from datetime import timedelta
import logging

from google.appengine.ext import ndb

from common.waterfall import failure_type
from libs import time_util
from model.wf_suspected_cl import WfSuspectedCL
from services import ci_failure
from waterfall import waterfall_config

_DEFAULT_AUTO_CREATE_REVERT_DAILY_THRESHOLD_COMPILE = 10
_DEFAULT_AUTO_COMMIT_REVERT_DAILY_THRESHOLD_COMPILE = 4


def _GetDailyNumberOfRevertedCulprits(limit):
  earliest_time = time_util.GetUTCNow() - timedelta(days=1)
  # TODO(chanli): improve the check for a rare case when two pipelines revert
  # at the same time.
  return WfSuspectedCL.query(
      ndb.AND(WfSuspectedCL.failure_type == failure_type.COMPILE,
              WfSuspectedCL.revert_created_time >= earliest_time)).count(limit)


def CanAutoCreateRevert():
  """Checks if Findit can auto create a revert.

  Findit can auto create a revert if both of below are True:
    1. Auto create revert for compile is turned on;
    2. The number of reverts in past 24 hours is less than the daily limit.
  """
  action_settings = waterfall_config.GetActionSettings()
  # Auto revert has been turned off.
  if not bool(action_settings.get('auto_create_revert_compile')):
    return False

  auto_create_revert_daily_threshold_compile = action_settings.get(
      'auto_create_revert_daily_threshold_compile',
      _DEFAULT_AUTO_CREATE_REVERT_DAILY_THRESHOLD_COMPILE)
  # Auto revert has exceeded daily limit.
  if _GetDailyNumberOfRevertedCulprits(
      auto_create_revert_daily_threshold_compile
  ) >= auto_create_revert_daily_threshold_compile:
    logging.info('Auto reverts for compile culprits on %s has met daily limit.',
                 time_util.FormatDatetime(time_util.GetUTCNow()))
    return False

  return True


def _GetDailyNumberOfCommits(limit):
  earliest_time = time_util.GetUTCNow() - timedelta(days=1)
  # TODO(chanli): improve the check for a rare case when two pipelines commit
  # at the same time.
  return WfSuspectedCL.query(
      ndb.AND(
          WfSuspectedCL.failure_type == failure_type.COMPILE,
          WfSuspectedCL.revert_committed_time >= earliest_time)).count(limit)


def CanAutoCommitRevertByFindit():
  """Checks if the revert can be auto committed by Findit.

  The revert can be committed if all of below are True:
    1. Auto revert and Auto commit is turned on;
    2. The number of commits of reverts in past 24 hours is less than the
      daily limit;
  """
  action_settings = waterfall_config.GetActionSettings()
  if (not bool(action_settings.get('auto_commit_revert_compile')) or
      not bool(action_settings.get('auto_create_revert_compile'))):
    return False

  auto_commit_revert_daily_threshold_compile = action_settings.get(
      'auto_commit_revert_daily_threshold_compile',
      _DEFAULT_AUTO_COMMIT_REVERT_DAILY_THRESHOLD_COMPILE)
  if _GetDailyNumberOfCommits(auto_commit_revert_daily_threshold_compile
                             ) >= auto_commit_revert_daily_threshold_compile:
    logging.info('Auto commits on %s has met daily limit.',
                 time_util.FormatDatetime(time_util.GetUTCNow()))
    return False

  return True


def ShouldTakeActionsOnCulprit(parameters):
  """Checks if the compile failure continues in later builds to determine
   should take actions on the culprit or not."""
  master_name, builder_name, build_number = parameters.build_key.GetParts()

  assert parameters.culprits

  if not ci_failure.GetLaterBuildsWithAnySameStepFailure(
      master_name, builder_name, build_number, ['compile']):
    # The compile failure stops, don't need to revert or send notification.
    logging.info(
        'No revert or notification needed for culprit(s) for '
        '%s/%s/%s since the compile failure has stopped.', master_name,
        builder_name, build_number)
    return False

  return True
