# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from common.findit_http_client import FinditHttpClient
from gae_libs.pipeline_wrapper import BasePipeline
from gae_libs.pipeline_wrapper import pipeline
from libs import analysis_status
from waterfall import build_util
from waterfall import buildbot
from waterfall.flake.lookback_algorithm import IsStable
from waterfall.flake.recursive_flake_pipeline import RecursiveFlakePipeline

_RUNNING_STATUSES = [analysis_status.PENDING, analysis_status.RUNNING]


class _CommitPositionRange():

  def __init__(self, earliest_commit_position, latest_commit_position):
    self.earliest_commit_position = earliest_commit_position
    self.latest_commit_position = latest_commit_position

  def ToDict(self):
    return {
        'earliest_commit_position': self.earliest_commit_position,
        'latest_commit_position': self.latest_commit_position
    }


def _BuildNumbersToCommitPositionsDict(data_points):
  """Maps the build numbers in data_points to their commit position ranges.

  Args:
    data_points: A list of DataPoint entities from a MasterFlakeAnalysis.

  Returns:
    A dict mapping the data points with build numbers to their commit position
        ranges as _CommitPositionRange objects.
  """
  build_numbers_to_positions = {}

  for data_point in data_points:
    if data_point.build_number is None:  # Skip try job data points.
      continue
    if (data_point.previous_build_commit_position is not None and
        data_point.commit_position is not None):
      build_numbers_to_positions[data_point.build_number] = (
          _CommitPositionRange(data_point.previous_build_commit_position + 1,
                               data_point.commit_position))

  return build_numbers_to_positions


def _GetBoundedRangeForCommitPosition(commit_position,
                                      builds_to_commit_positions):
  """Gets the range (lower_bound, upper_bound] that contains commit_position.

  Args:
    commit_position (int): The commit position a user may be requesting
        analysis on.
    builds_to_commit_positions (dict): A dict representation of an
        analysis' existing data points used to estimate a good starting build
        number to search for the actual nearest containing build number.

  Returns:
    lower_bound (int), upper_bound (int): The range of build numbers that
        contains the desired commit_position, at or before upper_bound and
        ahead of lower_bound. If commit_position is before the earliest known
        build number's commit range, returns (None, earliest build) indicating
        no lower bound could be determined with existing data points. If
        commit_position is ahead of the last known build number's commit
        position, returns (latest build, None) indicating no upper bound could
        be determined with existing data points. If no information is provided
        in builds_to_commit_position, returns (None, None). The calling code
        should be responsible for checking the returned bounds and deciding what
        to do if either lower_bound or upper_bound are unknown before getting a
        tighter bound.
  """
  if not builds_to_commit_positions:
    return None, None

  build_numbers = sorted(builds_to_commit_positions.iterkeys(), reverse=True)

  # Check if the requested commit position is before the earliest known build
  # number's earliest commit.
  earliest_build_number = build_numbers[-1]
  earliest_commit_position = (builds_to_commit_positions[earliest_build_number]
                              .earliest_commit_position)
  if commit_position < earliest_commit_position:
    return None, earliest_build_number

  # Check if the requested commit position is after the latest known build
  # number's latest commit.
  latest_build_number = build_numbers[0]
  latest_commit_position = (
      builds_to_commit_positions[latest_build_number].latest_commit_position)
  if commit_position > latest_commit_position:
    return latest_build_number, None

  # The requested commit position is within the range of already-processed build
  # numbers.
  upper_bound = latest_build_number
  lower_bound = earliest_build_number
  for build_number in build_numbers:  # pragma: no branch
    commit_range = builds_to_commit_positions[build_number]
    if (commit_position >= commit_range.earliest_commit_position and
        commit_position <= commit_range.latest_commit_position):
      # Exact match.
      return build_number, build_number

    if commit_range.latest_commit_position > commit_position:
      upper_bound = build_number
    else:
      lower_bound = build_number
      break

  return lower_bound, upper_bound


def _GetBoundedRangeFromBuild(commit_position, master_name, builder_name,
                              build_number):
  build_info = build_util.GetBuildInfo(master_name, builder_name, build_number)
  if build_info.commit_position == commit_position:
    return build_number, build_number
  elif build_info.commit_position > commit_position:
    return None, build_number
  else:
    return build_number, None


def _GetEarliestContainingBuildNumber(commit_position, master_flake_analysis):
  """Gets the nearest build number containing commit_position within range.

    If the requested commit position falls before build number 0, 0 is returned.
    If the requested commit position is beyond what there are build numbers for,
    e.g. the last build number is 1000 at commit position 5000 and the user
    selects 5001+, 1000 is returned.

  Args:
    commit_position (int): The desired commit position to find the nearest
        build number that contains this commit.
    master_flake_analysis (MasterFlakeAnalysis): The original analysis whose
        data points will be used to calculate the nearest build number to
        commit_position.

  Returns:
    The nearest build (BuildInfo) that contains commit_position.
  """
  master_name = master_flake_analysis.master_name
  builder_name = master_flake_analysis.builder_name
  build_number = master_flake_analysis.build_number
  data_points = master_flake_analysis.data_points
  build_numbers_to_commit_positions = _BuildNumbersToCommitPositionsDict(
      data_points)

  if not build_numbers_to_commit_positions:
    # Fallback to the triggering build number.
    lower_bound, upper_bound = _GetBoundedRangeFromBuild(
        commit_position, master_name, builder_name, build_number)
  else:
    lower_bound, upper_bound = _GetBoundedRangeForCommitPosition(
        commit_position, build_numbers_to_commit_positions)

  if lower_bound is not None and lower_bound == upper_bound:
    return lower_bound

  return build_util.GetEarliestContainingBuild(master_name, builder_name,
                                               lower_bound, upper_bound,
                                               commit_position).build_number


def _RemoveStablePointsWithinRange(analysis, lower_bound_build_number,
                                   upper_bound_build_number,
                                   minimum_iterations):
  """Clears an analysis' data points within a commit position range."""
  algorithm_settings = analysis.algorithm_parameters.get('swarming_rerun')
  lower_flake_threshold = algorithm_settings.get('lower_flake_threshold')
  upper_flake_threshold = algorithm_settings.get('upper_flake_threshold')

  filtered_data_points = analysis.GetDataPointsWithinBuildNumberRange(
      lower_bound_build_number, upper_bound_build_number)
  any_changes = False
  for data_point in filtered_data_points:
    if (data_point.iterations < minimum_iterations and IsStable(
        data_point.pass_rate, lower_flake_threshold, upper_flake_threshold)):
      # Flaky points with more iterations will still be flaky, however stable
      # points with too few iterations cannot be trusted and should be removed.
      analysis.RemoveDataPointWithCommitPosition(data_point.commit_position)
      any_changes = True

  if any_changes:
    analysis.put()


def _CanStartManualAnalysis(analysis):
  return (analysis.status not in _RUNNING_STATUSES and
          analysis.try_job_status not in _RUNNING_STATUSES)


class RegressionRangeAnalysisPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  # Unused argument - pylint: disable=W0613
  def run(self, analysis_urlsafe_key, lower_bound_commit_position,
          upper_bound_commit_position, iterations_to_rerun):
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    if not _CanStartManualAnalysis(analysis):
      return

    lower_bound_build_number = _GetEarliestContainingBuildNumber(
        lower_bound_commit_position, analysis)
    upper_bound_build_number = _GetEarliestContainingBuildNumber(
        upper_bound_commit_position, analysis)
    step_metadata = buildbot.GetStepLog(
        analysis.master_name, analysis.builder_name, analysis.build_number,
        analysis.step_name, FinditHttpClient(), 'step_metadata')

    _RemoveStablePointsWithinRange(analysis, lower_bound_build_number,
                                   upper_bound_build_number,
                                   iterations_to_rerun)

    logging.info('Analyzing manually-input regression range [%d:%d]',
                 lower_bound_commit_position, upper_bound_commit_position)
    logging.info('Nearest build number range: [%d:%d]',
                 lower_bound_build_number, upper_bound_build_number)

    yield RecursiveFlakePipeline(
        analysis_urlsafe_key,
        upper_bound_build_number,
        lower_bound_build_number,
        upper_bound_build_number,
        iterations_to_rerun,
        step_metadata=step_metadata)
