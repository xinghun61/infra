# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import timedelta
import logging
import random

from common import appengine_util
from common import constants
from common.pipeline_wrapper import BasePipeline
from common.pipeline_wrapper import pipeline
from libs import time_util
from model import analysis_status
from model import result_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import waterfall_config
from waterfall.flake import confidence
from waterfall.flake import recursive_flake_try_job_pipeline
from waterfall.flake.recursive_flake_try_job_pipeline import (
    RecursiveFlakeTryJobPipeline)
from waterfall.flake.update_flake_bug_pipeline import UpdateFlakeBugPipeline
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)


_NO_BUILD_NUMBER = -1


def _UpdateAnalysisStatusUponCompletion(
    analysis, suspected_build, status, error, build_confidence_score=None):
  if suspected_build == _NO_BUILD_NUMBER:
    analysis.end_time = time_util.GetUTCNow()
    analysis.result_status = result_status.NOT_FOUND_UNTRIAGED
  else:
    analysis.suspected_flake_build_number = suspected_build

  analysis.error = error
  analysis.status = status
  analysis.confidence_in_suspected_build = build_confidence_score

  analysis.put()


def _GetETAToStartAnalysis(manually_triggered):
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

  now_at_pst = time_util.GetDatetimeInTimezone(
      'US/Pacific', time_util.GetUTCNowWithTimezone())
  if now_at_pst.weekday() >= 5:  # PST Saturday or Sunday.
    return time_util.GetUTCNow()

  if now_at_pst.hour < 11 or now_at_pst.hour >= 18:  # Before 11am or after 6pm.
    return time_util.GetUTCNow()

  # Set ETA time to 6pm, and also with a random latency within 30 minutes to
  # avoid sudden burst traffic to Swarming.
  diff = timedelta(hours=18 - now_at_pst.hour,
                   minutes=-now_at_pst.minute,
                   seconds=-now_at_pst.second + random.randint(0, 30 * 60),
                   microseconds=-now_at_pst.microsecond)
  eta = now_at_pst + diff

  # Convert back to UTC.
  return time_util.GetDatetimeInTimezone('UTC', eta)


def _IsSwarmingTaskSufficientForCacheHit(
    flake_swarming_task, number_of_iterations):
  """Determines whether or not a swarming task is sufficient for a cache hit.

  Args:
    flake_swarming_task (FlakeSwarmingTask): The task to be examined.
    number_of_iterations (int): The minimum number of iterations
      flake_swarming_task needs to have run in order to count as a cache hit.

  Returns:
    A bool whether or not flake_swarming_task is sufficient to be a cache hit.
  """
  # Swarming task must exist.
  if not flake_swarming_task:
    return False

  # Cached swarming task's numbers must be thorough enough.
  if flake_swarming_task.tries < number_of_iterations:
    return False

  # Cached swarming task must either be scheduled, in progress, or completed.
  return flake_swarming_task.status in [analysis_status.PENDING,
                                        analysis_status.RUNNING,
                                        analysis_status.COMPLETED]


def _GetBestBuildNumberToRun(
    master_name, builder_name, preferred_run_build_number, step_name, test_name,
    step_size, number_of_iterations):
  """Finds the optimal nearby swarming task build number to use for a cache hit.

  Builds are searched back looking for something either already completed or in
  progress. Completed builds are returned immediately, whereas for those in
  progress the closer the build number is to the original, the higher priority
  it is given.

  Args:
    master_name (str): The name of the master for this flake analysis.
    builder_name (str): The name of the builder for this flake analysis.
    preferred_run_build_number (int): The originally-requested build number to
      run the swarming task on.
    step_name (str): The name of the step to run swarming on.
    test_name (str): The name of the test to run swarming on.
    step_size (int): The distance of the last preferred build number that was
      called on this analysis. Used for determining the lookback threshold.
    number_of_iterations (int): The number of iterations being requested for
      the swarming task that is to be performed. Used to determine a sufficient
      cache hit.

  Returns:
    build_number (int): The best build number to analyze for this iteration of
      the flake analysis.
  """
  # Looks forward or backward up to half of step_size.
  possibly_cached_build_numbers = _GetListOfNearbyBuildNumbers(
      preferred_run_build_number, step_size / 2)
  candidate_build_number = None
  candidate_flake_swarming_task_status = None

  for build_number in possibly_cached_build_numbers:
    cached_flake_swarming_task = FlakeSwarmingTask.Get(
        master_name, builder_name, build_number, step_name, test_name)
    sufficient = _IsSwarmingTaskSufficientForCacheHit(
        cached_flake_swarming_task, number_of_iterations)

    if sufficient:
      if cached_flake_swarming_task.status == analysis_status.COMPLETED:
        # Found a nearby swarming task that's already done.
        return build_number

      # Keep searching, but keeping this candidate in mind. Pending tasks are
      # considered, but running tasks are given higher priority.
      # TODO(lijeffrey): A further optimization can be to pick the swarming
      # task with the earliest ETA.
      if (candidate_build_number is None or
          (candidate_flake_swarming_task_status == analysis_status.PENDING and
           cached_flake_swarming_task.status == analysis_status.RUNNING)):
        # Either no previous candidate or a better candidate was found.
        candidate_build_number = build_number
        candidate_flake_swarming_task_status = cached_flake_swarming_task.status

  # No cached build nearby deemed adequate could be found.
  return candidate_build_number or preferred_run_build_number


def _GetListOfNearbyBuildNumbers(preferred_run_build_number, maximum_threshold):
  """Gets a list of numbers within range near preferred_run_build_number.

  Args:
    preferred_run_build_number (int): Assumed to be a positive number.
    maximum_threshold (int): A non-negative number for how far in either
    direction to look.

  Returns:
    A list of nearby numbers within maximum_threshold before and after
    preferred_run_build_number, ordered by closest to farthest. For example, if
    preferred_run_build_number is 1000 and maximum_threshold is 2, return
    [1000, 999, 1001, 998, 1002].
  """
  if maximum_threshold >= preferred_run_build_number:
    # Build numbers are always assumed to start from 1, so don't include
    # anything before that.
    return range(1, preferred_run_build_number + maximum_threshold + 1)

  nearby_build_numbers = [preferred_run_build_number]

  for i in range(1, maximum_threshold + 1):
    nearby_build_numbers.append(preferred_run_build_number - i)
    nearby_build_numbers.append(preferred_run_build_number + i)

  return nearby_build_numbers


class RecursiveFlakePipeline(BasePipeline):

  def __init__(self, *args, **kwargs):
    super(RecursiveFlakePipeline, self).__init__(*args, **kwargs)
    self.manually_triggered = kwargs.get('manually_triggered', False)

  def StartOffPSTPeakHours(self, *args, **kwargs):
    """Starts the pipeline off PST peak hours if not triggered manually."""
    kwargs['eta'] = _GetETAToStartAnalysis(self.manually_triggered)
    self.start(*args, **kwargs)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, preferred_run_build_number,
          step_name, test_name, version_number, triggering_build_number,
          manually_triggered=False, use_nearby_neighbor=False, step_size=0):
    """Pipeline to determine the regression range of a flaky test.

    Args:
      master_name (str): The master name.
      builder_name (str): The builder name.
      preferred_run_build_number (int): The build number the check flake
        algorithm should perform a swarming rerun on, but may be overridden to
        use the results of a nearby neighbor if use_nearby_neighbor is True.
      step_name (str): The step name.
      test_name (str): The test name.
      version_number (int): The version to save analysis results and data to.
      triggering_build_number (int): The build number that triggered this
        analysis.
      manually_triggered (bool): True if the analysis is from manual request,
        like by a Chromium sheriff.
      use_nearby_neighbor (bool): Whether the optimization for using the
        swarming results of a nearby build number, if available, should be used
        in place of triggering a new swarming task on
        preferred_run_build_number.
      step_size (int): The difference in build numbers since the last call to
        RecursiveFlakePipeline to determine the bounds for how far a nearby
        build's swarming task results should be used. Only relevant if
        use_nearby_neighbor is True.
    Returns:
      A dict of lists for reliable/flaky tests.
    """
    flake_analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, triggering_build_number, step_name,
        test_name, version=version_number)
    logging.info(
        'Running RecursiveFlakePipeline on MasterFlakeAnalysis %s/%s/%s/%s/%s',
        master_name, builder_name, triggering_build_number, step_name,
        test_name)
    logging.info(
        'MasterFlakeAnalysis %s version %s', flake_analysis, version_number)

    if flake_analysis.status != analysis_status.RUNNING:  # pragma: no branch
      flake_analysis.status = analysis_status.RUNNING
      flake_analysis.start_time = time_util.GetUTCNow()
      flake_analysis.put()

    # TODO(lijeffrey): Allow custom parameters supplied by user.
    iterations = waterfall_config.GetCheckFlakeSettings().get(
        'iterations_to_rerun')
    actual_run_build_number = _GetBestBuildNumberToRun(
        master_name, builder_name, preferred_run_build_number, step_name,
        test_name, step_size, iterations) if use_nearby_neighbor else (
            preferred_run_build_number)

    # Call trigger pipeline (flake style).
    task_id = yield TriggerFlakeSwarmingTaskPipeline(
        master_name, builder_name, actual_run_build_number, step_name,
        [test_name])

    with pipeline.InOrder():
      yield ProcessFlakeSwarmingTaskResultPipeline(
          master_name, builder_name, actual_run_build_number, step_name,
          task_id, triggering_build_number, test_name, version_number)
      yield NextBuildNumberPipeline(
          master_name, builder_name, triggering_build_number,
          actual_run_build_number, step_name, test_name, version_number,
          use_nearby_neighbor=use_nearby_neighbor,
          manually_triggered=manually_triggered)


def _IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold):
  return (
      pass_rate < lower_flake_threshold or pass_rate > upper_flake_threshold)


def _GetNextBuildNumber(data_points, flake_settings):
  """Finds the next build to be checked flakiness on, or gets final result.

  Args:
    data_points (list): A list of data points of already-completed tasks
        for this analysis. Data_points are sorted by build_numbers in descending
        order.
    flake_settings (dict): A dict of parameters for algorithms.

  Returns:
    (next_build_number, suspected_build): The next build number to check
        and suspected build number that the flakiness was introduced in.
        If needs to check next_build_number, suspected_build will be
        _NO_BUILD_NUMBER; If suspected_build is found, next_build_number will be
        _NO_BUILD_NUMBER; If no findings eventually, both will be
        _NO_BUILD_NUMBER.
  """
  # A description of this algorithm can be found at:
  # https://docs.google.com/document/d/1wPYFZ5OT998Yn7O8wGDOhgfcQ98mknoX13AesJaS6ig/edit
  # Get the last result.
  lower_flake_threshold = flake_settings.get('lower_flake_threshold')
  upper_flake_threshold = flake_settings.get('upper_flake_threshold')
  max_stable_in_a_row = flake_settings.get('max_stable_in_a_row')
  max_flake_in_a_row = flake_settings.get('max_flake_in_a_row')
  max_dive_in_a_row = flake_settings.get('max_dive_in_a_row')
  dive_rate_threshold = flake_settings.get('dive_rate_threshold')

  stables_in_a_row = 0
  flakes_in_a_row = 0
  dives_in_a_row = 0
  stables_happened = False
  flakes_first = 0
  flaked_out = False
  next_build_number = 0

  for i in xrange(len(data_points)):
    pass_rate = data_points[i].pass_rate
    build_number = data_points[i].build_number
    if pass_rate < 0:   # Test doesn't exist in this build.
      if flaked_out or flakes_first:
        stables_in_a_row += 1
        lower_boundary = data_points[i - stables_in_a_row + 1].build_number
        return lower_boundary + 1, _NO_BUILD_NUMBER
      else:  # No flaky region has been identified, no findings.
        return _NO_BUILD_NUMBER, _NO_BUILD_NUMBER

    elif _IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold):
      stables_in_a_row += 1
      flakes_in_a_row = 0
      dives_in_a_row = 0
      stables_happened = True

      # TODO(http://crbug.com/670888): Pin point a stable build rather than
      # looking for stable region to further narrow down the sequential search
      # range.
      if stables_in_a_row <= max_stable_in_a_row:
        # No stable region yet, keep searching.
        next_build_number = build_number - 1
        continue
      # Stable region found.
      if not flaked_out and not flakes_first:
        # Already stabled_out but no flake region yet, no findings.
        return _NO_BUILD_NUMBER, _NO_BUILD_NUMBER

      # Flake region is also found, ready for sequential search.
      lower_boundary_index = i - stables_in_a_row + 1
      lower_boundary = data_points[lower_boundary_index].build_number
      previous_build = data_points[lower_boundary_index - 1].build_number
      if previous_build == lower_boundary + 1:
        # Sequential search is Done.
        return _NO_BUILD_NUMBER, previous_build
      # Continue sequential search.
      return lower_boundary + 1, _NO_BUILD_NUMBER

    else:  # Flaky result.
      flakes_in_a_row += 1
      stables_in_a_row = 0

      if flakes_in_a_row > max_flake_in_a_row:  # Identified a flaky region.
        flaked_out = True

      if not stables_happened:
        # No stables yet.
        flakes_first += 1

      # Check the pass_rate of previous run, if this is the first data_point,
      # consider the virtual previous run is stable.
      previous_pass_rate = data_points[i - 1].pass_rate if i > 0 else 0
      if _IsStable(
          previous_pass_rate, lower_flake_threshold, upper_flake_threshold):
        next_build_number = build_number - flakes_in_a_row
        continue

      # Checks for dives. A dive is a sudden drop in pass rate.
      if pass_rate - previous_pass_rate > dive_rate_threshold:
        # Possibly a dive just happened.
        # Set dives_in_a_row to one since this is the first sign of diving.
        # For cases where we have pass rates like 0.1, 0.51, 0.92, we will use
        # the earliest dive.
        dives_in_a_row = 1
      elif previous_pass_rate - pass_rate > dive_rate_threshold:
        # A rise just happened, sets dives_in_a_row back to 0.
        dives_in_a_row = 0
      else:
        # Two last results are close, increases dives_in_a_row if not 0.
        dives_in_a_row = dives_in_a_row + 1 if dives_in_a_row else 0

      if dives_in_a_row <= max_dive_in_a_row:
        step_size = 1 if dives_in_a_row else flakes_in_a_row
        next_build_number = build_number - step_size
        continue

      # Dived out.
      # Flake region must have been found, ready for sequential search.
      lower_boundary_index = i - dives_in_a_row + 1
      lower_boundary = data_points[lower_boundary_index].build_number
      build_after_lower_boundary = (
          data_points[lower_boundary_index - 1].build_number)
      if build_after_lower_boundary == lower_boundary + 1:
        # Sequential search is Done.
        return _NO_BUILD_NUMBER, build_after_lower_boundary
      # Sequential search.
      return lower_boundary + 1, _NO_BUILD_NUMBER

  return next_build_number, _NO_BUILD_NUMBER


class NextBuildNumberPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  # Unused argument - pylint: disable=W0613
  def run(
      self, master_name, builder_name, triggering_build_number,
      current_build_number, step_name, test_name, version_number,
      use_nearby_neighbor=False, manually_triggered=False):
    # Get MasterFlakeAnalysis success list corresponding to parameters.
    analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, triggering_build_number, step_name,
        test_name, version=version_number)

    flake_swarming_task = FlakeSwarmingTask.Get(
        master_name, builder_name, current_build_number, step_name, test_name)

    # Don't call another pipeline if we fail.
    if flake_swarming_task.status == analysis_status.ERROR:
      # Report the last flake swarming task's error that it encountered.
      # TODO(lijeffrey): Another neighboring swarming task may be needed in this
      # one's place instead of failing altogether.
      error = flake_swarming_task.error or {
          'error': 'Swarming task failed',
          'message': 'The last swarming task did not complete as expected'
      }

      _UpdateAnalysisStatusUponCompletion(
          analysis, None, analysis_status.ERROR, error)
      logging.error('Error in Swarming task')
      yield UpdateFlakeBugPipeline(analysis.key.urlsafe())
      return

    flake_settings = waterfall_config.GetCheckFlakeSettings()
    data_points = sorted(
        analysis.data_points, key=lambda k: k.build_number,
        reverse=True)
    # Figure out what build_number to trigger a swarming rerun on next, if any.
    next_build_number, suspected_build = _GetNextBuildNumber(
        data_points, flake_settings)

    max_build_numbers_to_look_back = flake_settings.get(
        'max_build_numbers_to_look_back')
    last_build_number = max(
        0, triggering_build_number - max_build_numbers_to_look_back)

    if (next_build_number < last_build_number or
        next_build_number >= triggering_build_number):  # Finished.
      build_confidence_score = None
      if suspected_build != _NO_BUILD_NUMBER:
        # Use steppiness as the confidence score.
        build_confidence_score = confidence.SteppinessForBuild(
            analysis.data_points, suspected_build)

      # Update suspected build and the confidence score.
      _UpdateAnalysisStatusUponCompletion(
          analysis, suspected_build, analysis_status.COMPLETED,
          None, build_confidence_score=build_confidence_score)

      if build_confidence_score is None or build_confidence_score < 0.6:
        # If no suspected build or confidence is too low, bail out on try jobs.
        # Based on analysis of historical data, 60% confidence could filter out
        # almost all false positives.
        logging.info('Skipping try jobs due to insufficient confidence')
      else:
        # Hook up with try-jobs.
        suspected_build_point = analysis.GetDataPointOfSuspectedBuild()

        if suspected_build_point and suspected_build_point.blame_list:
          if len(suspected_build_point.blame_list) > 1:
            logging.info('Running try-jobs against commits in suspected build')
            start_commit_position = suspected_build_point.commit_position - 1
            start_revision = suspected_build_point.GetRevisionAtCommitPosition(
                start_commit_position)
            yield RecursiveFlakeTryJobPipeline(
                analysis.key.urlsafe(), start_commit_position, start_revision)
            return  # No update to bug yet.
          else:
            # Single commit is the culprit.
            logging.info('Single commit in the blame list of suspected build')
            culprit_confidence_score = confidence.SteppinessForCommitPosition(
                analysis.data_points, suspected_build_point.commit_position)
            culprit = recursive_flake_try_job_pipeline.CreateCulprit(
                suspected_build_point.git_hash,
                suspected_build_point.commit_position,
                culprit_confidence_score)

            analysis.culprit = culprit
            analysis.put()
        else:
          logging.info('No suspected build or empty blame list')

      yield UpdateFlakeBugPipeline(analysis.key.urlsafe())
      return

    pipeline_job = RecursiveFlakePipeline(
        master_name, builder_name, next_build_number, step_name, test_name,
        version_number, triggering_build_number,
        manually_triggered=manually_triggered,
        use_nearby_neighbor=use_nearby_neighbor,
        step_size=(current_build_number - next_build_number))
    # Disable attribute 'target' defined outside __init__ pylint warning,
    # because pipeline generates its own __init__ based on run function.
    pipeline_job.target = (  # pylint: disable=W0201
        appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND))
    pipeline_job.StartOffPSTPeakHours(
        queue_name=self.queue_name or constants.DEFAULT_QUEUE)
