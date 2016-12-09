# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import timedelta
import logging
import random
import textwrap

from common import appengine_util
from common import constants
from common.pipeline_wrapper import BasePipeline
from libs import time_util
from model import analysis_status
from model import result_status
from model.flake.flake_swarming_task import FlakeSwarmingTask
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from waterfall import waterfall_config
from waterfall.post_comment_to_bug_pipeline import PostCommentToBugPipeline
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)


def _UpdateBugWithResult(analysis, queue_name):
  """Updates attached bug for the flakiness trend."""
  if (not analysis.bug_id or
      not analysis.algorithm_parameters.get('update_monorail_bug')):
    return False

  comment = textwrap.dedent("""
  Findit has generated the flakiness trend for this flake in the test config
  "%s / %s / %s" by rerunning the test %s times on Swarming with build artifacts
  from Waterfall. Please visit
    https://findit-for-me.appspot.com/waterfall/flake?key=%s\n
  Automatically posted by the findit-for-me app (https://goo.gl/YTKnaU).
  This feature is in alpha version. Feedback is welcome using component
  Tools>Test>FindIt>Flakiness !""") % (
      analysis.original_master_name, analysis.original_builder_name,
      analysis.original_step_name,
      analysis.algorithm_parameters.get('iterations_to_rerun'),
      analysis.key.urlsafe())
  labels = ['AnalyzedByFindit']
  pipeline = PostCommentToBugPipeline(analysis.bug_id, comment, labels)
  pipeline.target = appengine_util.GetTargetNameForModule(
      constants.WATERFALL_BACKEND)
  pipeline.start(queue_name=queue_name)
  return True


def _UpdateAnalysisStatusUponCompletion(master_flake_analysis, status, error):
  master_flake_analysis.end_time = time_util.GetUTCNow()
  master_flake_analysis.status = status

  if error:
    master_flake_analysis.error = error

  if master_flake_analysis.suspected_flake_build_number is not None:
    master_flake_analysis.result_status = result_status.FOUND_UNTRIAGED
  else:
    master_flake_analysis.result_status = result_status.NOT_FOUND_UNTRIAGED

  master_flake_analysis.put()


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
      # TODO (lijeffrey): A further optimization can be to pick the swarming
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
          step_name, test_name, version_number, master_build_number,
          flakiness_algorithm_results_dict, manually_triggered=False,
          use_nearby_neighbor=False, step_size=0):
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
      master_build_number (int): The build number of the Master_Flake_analysis.
      flakiness_algorithm_results_dict (dict): A dictionary used by
        NextBuildNumberPipeline
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
        master_name, builder_name, master_build_number, step_name, test_name,
        version=version_number)
    logging.info(
        'Running RecursiveFlakePipeline on MasterFlakeAnalysis %s/%s/%s/%s/%s',
        master_name, builder_name, master_build_number, step_name, test_name)
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
    # Pass the trigger pipeline into a process pipeline.
    test_result_future = yield ProcessFlakeSwarmingTaskResultPipeline(
        master_name, builder_name, actual_run_build_number,
        step_name, task_id, master_build_number, test_name, version_number)
    yield NextBuildNumberPipeline(
        master_name, builder_name, master_build_number,
        actual_run_build_number, step_name, test_name, version_number,
        test_result_future, flakiness_algorithm_results_dict,
        use_nearby_neighbor=use_nearby_neighbor,
        manually_triggered=manually_triggered)


def get_next_run(master_flake_analysis, flakiness_algorithm_results_dict):
  # A description of this algorithm can be found at:
  # https://docs.google.com/document/d/1wPYFZ5OT998Yn7O8wGDOhgfcQ98mknoX13AesJaS6ig/edit
  # Get the last result.
  last_result = master_flake_analysis.data_points[-1].pass_rate
  cur_run = min([d.build_number for d in master_flake_analysis.data_points])
  flake_settings = waterfall_config.GetCheckFlakeSettings()
  lower_flake_threshold = flake_settings.get('lower_flake_threshold')
  upper_flake_threshold = flake_settings.get('upper_flake_threshold')
  max_stable_in_a_row = flake_settings.get('max_stable_in_a_row')
  max_flake_in_a_row = flake_settings.get('max_flake_in_a_row')

  if last_result < 0:  # Test doesn't exist in the current build number.
    flakiness_algorithm_results_dict['stable_in_a_row'] += 1
    flakiness_algorithm_results_dict['stabled_out'] = True
    flakiness_algorithm_results_dict['flaked_out'] = True
    flakiness_algorithm_results_dict['lower_boundary_result'] = 'STABLE'

    lower_boundary = master_flake_analysis.data_points[
        -flakiness_algorithm_results_dict['stable_in_a_row']].build_number

    flakiness_algorithm_results_dict['lower_boundary'] = lower_boundary
    flakiness_algorithm_results_dict['sequential_run_index'] += 1
    return lower_boundary + 1

  elif (last_result < lower_flake_threshold or
        last_result > upper_flake_threshold):  # Stable result.
    flakiness_algorithm_results_dict['stable_in_a_row'] += 1
    flakiness_algorithm_results_dict['stables_happened'] = True

    if flakiness_algorithm_results_dict['flakes_first'] == 0:
      # First task is not flaky, makes flakes_first invalid.
      flakiness_algorithm_results_dict['flakes_first'] = None

    # TODO (chanli): Pin point a stable build rather than looking for stable
    # region to further narrow down the range for sequential search.
    # crbug.com/670888
    if (flakiness_algorithm_results_dict['stable_in_a_row'] >
        max_stable_in_a_row):
      flakiness_algorithm_results_dict['stabled_out'] = True
      # Flake region is also found, ready for sequential search.
      if (flakiness_algorithm_results_dict['flaked_out'] or
          flakiness_algorithm_results_dict['flakes_first']):
        if flakiness_algorithm_results_dict['lower_boundary']:
          lower_boundary = flakiness_algorithm_results_dict['lower_boundary']
        else:
          lower_boundary = master_flake_analysis.data_points[
            -flakiness_algorithm_results_dict['stable_in_a_row']].build_number
          flakiness_algorithm_results_dict['lower_boundary'] = lower_boundary
        flakiness_algorithm_results_dict['sequential_run_index'] += 1
        return lower_boundary + 1
      else:  # Already stabled_out but not flaked_out, no findings.
        return -1

    if ((flakiness_algorithm_results_dict['flaked_out'] or
         flakiness_algorithm_results_dict['flakes_first']) and
        not flakiness_algorithm_results_dict['stabled_out'] and
        not flakiness_algorithm_results_dict['lower_boundary']):
      # Identified a candidate for the lower boundary.
      # Latest stable point to the left of a flaky region.
      flakiness_algorithm_results_dict['lower_boundary'] = cur_run
      flakiness_algorithm_results_dict['lower_boundary_result'] = 'STABLE'
    flakiness_algorithm_results_dict['flakes_in_a_row'] = 0
    step_size = flakiness_algorithm_results_dict['stable_in_a_row'] + 1
    return cur_run - step_size

  else:
    # Flaky result.
    flakiness_algorithm_results_dict['flakes_in_a_row'] += 1

    if not flakiness_algorithm_results_dict['stables_happened']:
      # No stables yet.
      flakiness_algorithm_results_dict['flakes_first'] += 1

    if (flakiness_algorithm_results_dict['flakes_in_a_row'] >
        max_flake_in_a_row):  # Identified a flaky region.
      flakiness_algorithm_results_dict['flaked_out'] = True

    if ((flakiness_algorithm_results_dict['flaked_out'] or
         flakiness_algorithm_results_dict['flakes_first']) and
        not flakiness_algorithm_results_dict['stabled_out']):
      # Identified a candidate for the upper boundary.
      # Earliest flaky point to the right of a stable region.
      flakiness_algorithm_results_dict['upper_boundary'] = cur_run
      flakiness_algorithm_results_dict['lower_boundary'] = None
    flakiness_algorithm_results_dict['stable_in_a_row'] = 0
    step_size = flakiness_algorithm_results_dict['flakes_in_a_row'] + 1
    return cur_run - step_size


def sequential_next_run(
    master_flake_analysis, flakiness_algorithm_results_dict):
  last_result = master_flake_analysis.data_points[-1].pass_rate
  last_result_status = 'FLAKE'
  flake_settings = waterfall_config.GetCheckFlakeSettings()
  lower_flake_threshold = flake_settings.get('lower_flake_threshold')
  upper_flake_threshold = flake_settings.get('upper_flake_threshold')

  if (last_result < lower_flake_threshold or
      last_result > upper_flake_threshold):
    last_result_status = 'STABLE'
  if flakiness_algorithm_results_dict['sequential_run_index'] > 0:
    if (last_result_status !=
        flakiness_algorithm_results_dict['lower_boundary_result']):
      master_flake_analysis.suspected_flake_build_number = (
          flakiness_algorithm_results_dict['lower_boundary'] +
          flakiness_algorithm_results_dict['sequential_run_index'])
      master_flake_analysis.put()
      return -1
  flakiness_algorithm_results_dict['sequential_run_index'] += 1
  return (flakiness_algorithm_results_dict['lower_boundary'] +
          flakiness_algorithm_results_dict['sequential_run_index'])


class NextBuildNumberPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  # Unused argument - pylint: disable=W0613
  def run(self, master_name, builder_name, master_build_number,
          run_build_number, step_name, test_name, version_number,
          test_result_future, flakiness_algorithm_results_dict,
          use_nearby_neighbor=False, manually_triggered=False):

    # Get MasterFlakeAnalysis success list corresponding to parameters.
    master_flake_analysis = MasterFlakeAnalysis.GetVersion(
        master_name, builder_name, master_build_number, step_name, test_name,
        version=version_number)

    flake_swarming_task = FlakeSwarmingTask.Get(
        master_name, builder_name, run_build_number, step_name, test_name)

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
          master_flake_analysis, analysis_status.ERROR, error)
      return

    # Figure out what build_number to trigger a swarming rerun on next, if any.
    if flakiness_algorithm_results_dict['stabled_out']:
      next_run = sequential_next_run(
          master_flake_analysis, flakiness_algorithm_results_dict)
    else:
      next_run = get_next_run(
          master_flake_analysis, flakiness_algorithm_results_dict)
    if (next_run < flakiness_algorithm_results_dict['last_build_number'] or
        next_run >= master_build_number):
       # Finished.
      _UpdateAnalysisStatusUponCompletion(
          master_flake_analysis, analysis_status.COMPLETED, None)
      _UpdateBugWithResult(
          master_flake_analysis, self.queue_name or constants.DEFAULT_QUEUE)
      return

    pipeline_job = RecursiveFlakePipeline(
        master_name, builder_name, next_run, step_name, test_name,
        version_number, master_build_number,
        flakiness_algorithm_results_dict=flakiness_algorithm_results_dict,
        manually_triggered=manually_triggered,
        use_nearby_neighbor=use_nearby_neighbor,
        step_size=(run_build_number - next_run))
    # Disable attribute 'target' defined outside __init__ pylint warning,
    # because pipeline generates its own __init__ based on run function.
    pipeline_job.target = (  # pylint: disable=W0201
        appengine_util.GetTargetNameForModule(constants.WATERFALL_BACKEND))
    pipeline_job.StartOffPSTPeakHours(
        queue_name=self.queue_name or constants.DEFAULT_QUEUE)
