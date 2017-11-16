# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from gae_libs.pipeline_wrapper import BasePipeline
from waterfall import waterfall_config
from waterfall.flake import flake_analysis_util
from waterfall.flake import flake_constants
from waterfall.flake import lookback_algorithm


def _IsFinished(next_build_number, earliest_build_number, latest_build_number):
  """Determines whether or not to stop checking more build numbers.

    An analysis at the build number level is complete if the next suggested
    build number has already been run, is beyond the lower bound.
    If the build is out of bounds, then build-level analysis is done.

  Args:
    next_build_number (int): The proposed next build number to run.
    earliest_build_number (int): The lower bound build number to compare.
    latest_build_number (int): The upper bound build number to compare.

  Returns:
    (boolean) True if the analysis is finished, False otherwise.
  """
  return (next_build_number is None or
          next_build_number < earliest_build_number or
          next_build_number >= latest_build_number)


def _GetEarliestBuildNumber(lower_bound_build_number, triggering_build_number,
                            algorithm_settings):
  if lower_bound_build_number is not None:
    return lower_bound_build_number

  max_build_numbers_to_look_back = algorithm_settings.get(
      'max_build_numbers_to_look_back',
      flake_constants.DEFAULT_MAX_BUILD_NUMBERS)

  return max(0, triggering_build_number - max_build_numbers_to_look_back)


def _GetLatestBuildNumber(upper_bound_build_number, triggering_build_number):
  return upper_bound_build_number or triggering_build_number


class NextBuildNumberPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  # Unused argument - pylint: disable=W0613
  def run(self, analysis_urlsafe_key, current_build_number,
          lower_bound_build_number, upper_bound_build_number,
          user_specified_iterations):
    """Pipeline for determining the next build number to analyze.

    Args:
      analysis_urlsafe_key (str): The url-safe key to the MasterFlakeAnalysis
          being analyzed.
      current_build_number (int): The build number that has just been analyzed.
      lower_bound_build_number (int): The earliest build number to check, or
          None if not specified.
      upper_bound_build_number (int): The latest build number to check, or None
          if not specified.
      user_specified_iterations (int): The number of iterations to rerun as
          specified by the user. If None is passed, Findit will determine the
          number of iterations to rerun.

    Returns:
      (int) Next build number to run, or None if build-level analysis is done
          either due to finding a suspected build, the flake not being
          reproducible, or exceeding the maximum window to search with no
          findings.
    """
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    master_name = analysis.master_name
    builder_name = analysis.builder_name
    triggering_build_number = analysis.build_number
    step_name = analysis.step_name
    test_name = analysis.test_name

    logging.info('%s/%s/%s/%s/%s completed analysis on build number %s',
                 master_name, builder_name, triggering_build_number, step_name,
                 test_name, current_build_number)

    if not analysis.algorithm_parameters:
      analysis.Update(
          algorithm_parameters=waterfall_config.GetCheckFlakeSettings())
    algorithm_settings = analysis.algorithm_parameters.get('swarming_rerun')

    # Figure out what build_number to trigger a swarming rerun on next, if any.
    data_points_within_range = analysis.GetDataPointsWithinBuildNumberRange(
        lower_bound_build_number, upper_bound_build_number)
    logging.info(('%s/%s/%s/%s/%s Determining next data point to analyze based '
                  'on %s'), master_name, builder_name, triggering_build_number,
                 step_name, test_name, data_points_within_range)
    data_points = flake_analysis_util.NormalizeDataPointsByBuildNumber(
        data_points_within_range)

    # Next build number will be None if either a suspected build is identified
    # or the flake is not reproducible according to lookback_algorithm.
    next_build_number, _ = lookback_algorithm.GetNextRunPointNumber(
        data_points, algorithm_settings)

    earliest_build_number = _GetEarliestBuildNumber(
        lower_bound_build_number, triggering_build_number, algorithm_settings)
    latest_build_number = _GetLatestBuildNumber(upper_bound_build_number,
                                                triggering_build_number)
    # Ordering matters here -- we don't want to cull the latest data point if
    # the analysis is finished.
    if _IsFinished(next_build_number, earliest_build_number,
                   latest_build_number):
      # If we're finished, return None to RecursiveFlakePipeline to signal it.
      logging.info('%s/%s/%s/%s/%s Determined that the build '
                   'level analysis is complete.', master_name, builder_name,
                   triggering_build_number, step_name, test_name)
      return None

    logging.info('%s/%s/%s/%s/%s Returning the next build number to recursive'
                 'flake pipeline: %s', master_name, builder_name,
                 triggering_build_number, step_name, test_name,
                 next_build_number)

    return next_build_number
