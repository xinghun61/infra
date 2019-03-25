# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import timedelta
import logging
import random

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from infra_api_clients.swarming import swarming_util
from libs import time_util
from model.flake.analysis.flake_culprit import FlakeCulprit
from services import constants
from services import swarming
from services.flake_failure import flake_constants
from services.flake_failure import pass_rate_util
from waterfall import waterfall_config

_GIT_REPO = CachedGitilesRepository(FinditHttpClient(),
                                    constants.CHROMIUM_GIT_REPOSITORY_URL)


def _BotsAvailableForTask(step_metadata):
  """Check if there are available bots for a swarming task's dimensions.

  Args:
    step_metadata (dict): Info about a step to determine the bot's
        dimensions to query Swarming with about bot availability.

  Returns:
    (bool): Whether or not there are enough bots available to trigger the task
        immediately.
  """
  if not step_metadata:
    return False

  minimum_number_of_available_bots = (
      waterfall_config.GetSwarmingSettings().get(
          'minimum_number_of_available_bots',
          flake_constants.DEFAULT_MINIMUM_NUMBER_AVAILABLE_BOTS))
  minimum_percentage_of_available_bots = (
      waterfall_config.GetSwarmingSettings().get(
          'minimum_percentage_of_available_bots',
          flake_constants.DEFAULT_MINIMUM_PERCENTAGE_AVAILABLE_BOTS))
  dimensions = step_metadata.get('dimensions')
  bot_counts = swarming_util.GetBotCounts(swarming.SwarmingHost(), dimensions,
                                          FinditHttpClient)
  total_count = bot_counts.count or -1
  available_count = bot_counts.available or 0
  available_rate = float(available_count) / total_count

  return (available_count > minimum_number_of_available_bots and
          available_rate > minimum_percentage_of_available_bots)


def _CanStartAnalysis(step_metadata, retries, force):
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
           (case: _BotsAvailableForTask(step_metadata))
  """
  if force or retries > flake_constants.MAX_RETRY_TIMES:
    return True
  return _BotsAvailableForTask(step_metadata)


def CanStartAnalysisImmediately(step_metadata, retries, manually_triggered):
  """Determines whether an analysis can start immediately."""
  return (not ShouldThrottleAnalysis() or
          _CanStartAnalysis(step_metadata, retries, manually_triggered))


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
  assert retries >= 0, 'Cannot calculate delay without retries'

  if retries > flake_constants.MAX_RETRY_TIMES:
    delay_delta = GetETAToStartAnalysis(
        manually_triggered) - time_util.GetUTCNow()
    return int(delay_delta.total_seconds())
  else:
    delay_seconds = retries * flake_constants.BASE_COUNT_DOWN_SECONDS
    return delay_seconds


def GetETAToStartAnalysis(manually_triggered):
  """Returns an ETA as of a UTC datetime.datetime to start the analysis.

  If not urgent, Swarming tasks should be run off PST peak hours from 11am to
  6pm on workdays.

  Args:
    manually_triggered (bool): True if the analysis is from manual request, like
        by a Chromium sheriff.

  Returns:
    The ETA as of a UTC datetime.datetime to start the analysis.
  """
  if manually_triggered:
    # If the analysis is manually triggered, run it right away.
    return time_util.GetUTCNow()

  now_at_pst = time_util.GetPSTNow()
  if now_at_pst.weekday() >= 5:  # PST Saturday or Sunday.
    return time_util.GetUTCNow()

  if now_at_pst.hour < 11 or now_at_pst.hour >= 18:  # Before 11am or after 6pm.
    return time_util.GetUTCNow()

  # Set ETA time to 6pm, and also with a random latency within 30 minutes to
  # avoid sudden burst traffic to Swarming.
  diff = timedelta(
      hours=18 - now_at_pst.hour,
      minutes=-now_at_pst.minute,
      seconds=-now_at_pst.second + random.randint(0, 30 * 60),
      microseconds=-now_at_pst.microsecond)
  eta = now_at_pst + diff

  # Convert back to UTC.
  return time_util.ConvertPSTToUTC(eta)


def ShouldTakeAutoAction(analysis, rerun):
  """Determines whether auto action should be taken.

    Rules for auto actions:
      1. The analysis must not be a rerun to prevent spamming.
      2. The culprit cannot be stable failing --> flaky, as these are always
         false positives. Such instances should be interpreted separately as
         mentioned in crbug.com/809705.

  Args:
    analysis (MasterFlakeAnalysis): The analysis for which auto actions are to
      be performed.
    rerun (bool): Whether this is a rerun of an existing analysis.

  Returns:
    (bool) Whether or not auto actions should be performed.
  """
  if rerun:  # pragma: no branch
    analysis.LogInfo('Bailing out of auto actions for rerun')
    return False

  if analysis.culprit_urlsafe_key:  # pragma: no branch
    culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
    assert culprit, 'Culprit missing unexpectedly!'

    previous_data_point = analysis.FindMatchingDataPointWithCommitPosition(
        culprit.commit_position - 1)

    if pass_rate_util.IsStableFailing(previous_data_point.pass_rate):
      analysis.LogInfo(
          'Bailing out of auto action for stable failing --> flaky Refer to '
          'crbug.com/809705 for reference')
      return False

  return True


def FlakyAtMostRecentlyAnalyzedCommit(analysis):
  """Determines whether the most recently analyzed data point is flaky."""
  # Try flakiness_verification_data_points, falling back to main data_points.
  data_points_to_check = (
      analysis.flakiness_verification_data_points or analysis.data_points)
  assert data_points_to_check, (
      'Data points to check recent flakiness for analysis {} unexpectedly '
      'missing!'.format(analysis.key.urlsafe()))

  recent_data_point = sorted(
      data_points_to_check, key=lambda x: x.commit_position, reverse=True)[0]

  return not pass_rate_util.IsFullyStable(recent_data_point.pass_rate)


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
