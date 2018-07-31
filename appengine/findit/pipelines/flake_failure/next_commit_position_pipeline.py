# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from dto.int_range import IntRange
from dto.step_metadata import StepMetadata
from gae_libs.pipelines import SynchronousPipeline
from libs.structured_object import StructuredObject
from services import step_util
from services.flake_failure import heuristic_analysis
from services.flake_failure import lookback_algorithm
from services.flake_failure import next_commit_position_utils


class NextCommitPositionInput(StructuredObject):
  # The urlsafe-key to the MasterflakeAnalysius in progress.
  analysis_urlsafe_key = basestring

  # The upper and lower bound commit positions not to exceed.
  commit_position_range = IntRange

  # Info about the test to identify nearby IsolatedTargets.
  step_metadata = StepMetadata


class NextCommitPositionOutput(StructuredObject):
  # The next commit position that the flake analysis should run. Should be
  # mutually exclusive with culprit_commit_position.
  next_commit_position = int

  # The commit position of the identified culprit. Should be mutually
  # exclusive with next_commit_position.
  culprit_commit_position = int


class NextCommitPositionPipeline(SynchronousPipeline):

  input_type = NextCommitPositionInput
  output_type = NextCommitPositionOutput

  def RunImpl(self, parameters):
    """Pipeline for determining the next commit position to analyze."""

    analysis_urlsafe_key = parameters.analysis_urlsafe_key
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    master_name = analysis.master_name
    builder_name = analysis.builder_name
    specified_lower_bound = parameters.commit_position_range.lower
    specified_upper_bound = parameters.commit_position_range.upper

    data_points = analysis.GetDataPointsWithinCommitPositionRange(
        IntRange(lower=specified_lower_bound, upper=specified_upper_bound))

    # Data points must be sorted in reverse order by commit position before.
    data_points = sorted(
        data_points, key=lambda k: k.commit_position, reverse=True)

    # A suspected build id is available when there is a regression range that
    # spans a single build cycle. During this time, bisect is preferred to
    # exponential search.
    use_bisect = analysis.suspected_flake_build_number is not None
    latest_regression_range = analysis.GetLatestRegressionRange()

    calculated_next_commit_position, culprit_commit_position = (
        lookback_algorithm.GetNextCommitPosition(data_points, use_bisect,
                                                 latest_regression_range))

    if calculated_next_commit_position is None:
      # The analysis is finished according to the lookback algorithm.
      return NextCommitPositionOutput(
          next_commit_position=None,
          culprit_commit_position=culprit_commit_position)

    cutoff_commit_position = (
        next_commit_position_utils.GetEarliestCommitPosition(
            specified_lower_bound, specified_upper_bound))

    if calculated_next_commit_position < cutoff_commit_position:
      # Long-standing flake. Do not continue the analysis.
      return NextCommitPositionOutput(
          next_commit_position=None, culprit_commit_position=None)

    # Try the analysis' heuristic results first, if any.
    next_commit_position = (
        next_commit_position_utils.GetNextCommitPositionFromHeuristicResults(
            analysis_urlsafe_key))

    if next_commit_position is not None:
      # Heuristic results are available and should be tried first.
      assert not analysis.FindMatchingDataPointWithCommitPosition(
          next_commit_position), (
              'Existing heuristic results suggest commit position {} which has '
              'already been run'.format(next_commit_position))
      return NextCommitPositionOutput(
          next_commit_position=next_commit_position,
          culprit_commit_position=None)

    # Round off the next calculated commit position to the nearest builds on
    # both sides.
    target_name = parameters.step_metadata.isolate_target_name
    lower_bound_target, upper_bound_target = (
        step_util.GetBoundingIsolatedTargets(master_name, builder_name,
                                             target_name,
                                             calculated_next_commit_position))

    # Update the analysis' suspected build cycle if identified.
    analysis.UpdateSuspectedBuild(lower_bound_target, upper_bound_target)

    # When identifying the neighboring builds of the requested commit position,
    # heuristic analysis may become eligible if the neighboring builds are
    # adjacent to one another.
    if analysis.CanRunHeuristicAnalysis():
      # Run heuristic analysis if eligible and not yet already done.
      heuristic_analysis.RunHeuristicAnalysis(analysis)

      # Try the newly computed heuristic results if any were identified.
      next_commit_position = (
          next_commit_position_utils.GetNextCommitPositionFromHeuristicResults(
              analysis_urlsafe_key))
      if next_commit_position is not None:
        assert not analysis.FindMatchingDataPointWithCommitPosition(
            next_commit_position
        ), ('Newly run heuristic results suggest commit position {} which has '
            'already been run'.format(next_commit_position))
        return NextCommitPositionOutput(
            next_commit_position=next_commit_position,
            culprit_commit_position=None)

    # Pick the commit position of the returned neighboring builds that has not
    # yet been analyzed if possible, or the commit position itself when not.
    build_range = IntRange(
        lower=lower_bound_target.commit_position,
        upper=upper_bound_target.commit_position)
    actual_next_commit_position = (
        next_commit_position_utils.GetNextCommitPositionFromBuildRange(
            analysis, build_range, calculated_next_commit_position))
    assert not analysis.FindMatchingDataPointWithCommitPosition(
        actual_next_commit_position), (
            'Rounded-off commit position {} has already been run'.format(
                actual_next_commit_position))
    return NextCommitPositionOutput(
        next_commit_position=actual_next_commit_position,
        culprit_commit_position=culprit_commit_position)
