# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from dto.int_range import IntRange
from gae_libs.pipelines import SynchronousPipeline
from libs.structured_object import StructuredObject
from services import step_util
from services.flake_failure import lookback_algorithm
from services.flake_failure import next_commit_position_utils
from waterfall import build_util


class NextCommitPositionInput(StructuredObject):
  # The urlsafe-key to the MasterflakeAnalysius in progress.
  analysis_urlsafe_key = basestring

  # The upper and lower bound commit positions not to exceed.
  commit_position_range = IntRange


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
    use_bisect = analysis.suspected_flake_build_id is not None

    calculated_next_commit_position, culprit_commit_position = (
        lookback_algorithm.GetNextCommitPosition(data_points, use_bisect))

    if calculated_next_commit_position is None:
      # The analysis is finished according to the lookback algorithm.
      return NextCommitPositionOutput(
          next_commit_position=calculated_next_commit_position,
          culprit_commit_position=culprit_commit_position)

    cutoff_commit_position = (
        next_commit_position_utils.GetEarliestCommitPosition(
            specified_lower_bound, specified_upper_bound))

    if calculated_next_commit_position < cutoff_commit_position:
      # Long-standing flake. Do not continue the analysis.
      return NextCommitPositionOutput(
          next_commit_position=None, culprit_commit_position=None)

    # Round off the next calculated commit position to the nearest builds on
    # both sides.
    lower_bound_build, upper_bound_build = (
        step_util.GetValidBoundingBuildsForStep(
            master_name, builder_name, analysis.step_name, None, None,
            calculated_next_commit_position))

    # Update the analysis' suspected build cycle if identified.
    analysis.UpdateSuspectedBuildID(lower_bound_build, upper_bound_build)

    # Run heuristic analysis if eligible and not yet already done.
    if analysis.CanRunHeuristicAnalysis():  # pragma: no cover.
      # TODO(crbug.com/798228): Run heuristic analysis and consider results
      # first before falling back to the lookback algorithm's suggestions.
      pass

    # Pick the commit position of the returned neighboring builds that has not
    # yet been analyzed if possible, or the commit position itself when not.
    build_range = IntRange(
        lower=lower_bound_build.commit_position,
        upper=upper_bound_build.commit_position)
    actual_next_commit_position = (
        next_commit_position_utils.GetNextCommitPositionFromBuildRange(
            analysis, build_range, calculated_next_commit_position))

    return NextCommitPositionOutput(
        next_commit_position=actual_next_commit_position,
        culprit_commit_position=culprit_commit_position)
