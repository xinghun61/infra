# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import time_util
from model.flake.flake_culprit import FlakeCulprit
from services.flake_failure import flake_constants
from waterfall import waterfall_config
# TODO(crbug.com/809885): Merge into this module.
from waterfall.flake import flake_analysis_util

_GIT_REPO = CachedGitilesRepository(FinditHttpClient(),
                                    flake_constants.CHROMIUM_GIT_REPOSITORY_URL)


def CanStartAnalysis(step_metadata, retries, force):
  """Determines if an analysis should be started.

  Args:
    step_metadata (StepMetadata): Step metadata for the test, used to find bots.
    retries (int): Number of times this recursive flake pipeline has been
        rescheduled
    force (boolean): A forced rerun triggered through the UI.

  Returns:
    True if there are bots available or:
        1. If forced rerun, start the analysis right away without checking
           bot availability (case: force).
        2. If retries is more than the max, start the analysis right away
           because it was guaranteed to run off the peak hour as scheduled
           after retries. (case: retries > flake_constants.MAX_RETRY_TIMES)
        3. If there is available bot before/during the N retires, start the
           analysis right away.
           (case: BotsAvailableForTask(step_metadata))
  """
  if force or retries > flake_constants.MAX_RETRY_TIMES:
    return True
  return flake_analysis_util.BotsAvailableForTask(step_metadata)


def CanStartAnalysisImmediately(step_metadata, retries, manually_triggered):
  """Determines whether an analysis can start immediately."""
  return (not ShouldThrottleAnalysis() or
          CanStartAnalysis(step_metadata, retries, manually_triggered))


def CanFailedSwarmingTaskBeSalvaged(task):
  """Returns if the task has all the necessary fields."""
  if not task:
    return False
  return (task.iterations is not None and task.iterations > 0 and
          task.pass_count is not None and task.pass_count >= 0 and
          task.started_time is not None and task.completed_time is not None and
          task.completed_time > task.started_time and task.task_id is not None)


def CalculateDelaySecondsBetweenRetries(retries, manually_triggered):
  """Returns the number of seconds to wait before retrying analysis.

  Args:
    retries (int): The number of attempts already made.
    manually_triggered (bool): Whether the analysis was triggered as the result
        of a manual request.

  Returns:
    The number of seconds to wait between attempts for analyzing flakiness at
        a commit position.
  """
  assert retries >= 0

  if retries > flake_constants.MAX_RETRY_TIMES:
    delay_delta = flake_analysis_util.GetETAToStartAnalysis(
        manually_triggered) - time_util.GetUTCNow()
    return int(delay_delta.total_seconds())
  else:
    delay_seconds = retries * flake_constants.BASE_COUNT_DOWN_SECONDS
    return delay_seconds


def ShouldThrottleAnalysis():
  """Determines whether to throttle an analysis based on config."""
  flake_settings = waterfall_config.GetCheckFlakeSettings()
  return flake_settings.get('throttle_flake_analyses', True)


@ndb.transactional
def UpdateCulprit(analysis_urlsafe_key,
                  revision,
                  commit_position,
                  repo_name='chromium'):
  """Sets culprit information.

  Args:
    analysis_urlafe_key (str): The urlsafe-key to the MasterFlakeAnalysis to
        update culprit information for.
    revision (str): The culprit's chromium revision.
    commit_position (int): The culprit's commit position.
    repo_name (str): The name of the repo the culprit is in.
  """
  culprit = (
      FlakeCulprit.Get(repo_name, revision) or
      FlakeCulprit.Create(repo_name, revision, commit_position))

  needs_updating = False

  if culprit.url is None:
    change_log = _GIT_REPO.GetChangeLog(revision)

    if change_log:
      culprit.url = change_log.code_review_url or change_log.commit_url
      needs_updating = True
    else:
      logging.error('Unable to retrieve change logs for %s', revision)

  if analysis_urlsafe_key not in culprit.flake_analysis_urlsafe_keys:
    culprit.flake_analysis_urlsafe_keys.append(analysis_urlsafe_key)
    needs_updating = True

  if needs_updating:
    culprit.put()

  return culprit
