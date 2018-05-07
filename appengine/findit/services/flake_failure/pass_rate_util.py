# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utility functions for processing a flaky test's pass rates."""

from waterfall import waterfall_config
from waterfall.flake import flake_constants


def CalculateNewPassRate(existing_pass_rate, existing_iterations,
                         incoming_pass_rate, incoming_iterations):
  """Incorporates a new pass rate into an exsting one.

  Args:
    existing_pass_rate (float): The pass rate to merge into.
    exisitng_iterations (int): The number of iterations used to calculate the
        existing pass rate.
    incoming_pass_rate (float): The new pass rate to incorporate.
    incoming_iterations (int): The number of iterations used to calculate the
        incoming pass rate.

  Returns:
    (float): The new combined pass rate.
  """
  existing_pass_count = existing_pass_rate * existing_iterations
  incoming_pass_count = incoming_pass_rate * incoming_iterations

  return float(existing_pass_count + incoming_pass_count) / (
      existing_iterations + incoming_iterations)


def GetPassRate(swarming_task_output):
  """Determines a pass rate based on a swarming task's output.

  The passrate for an invalid swarming_task_output is undefined and may
  potentially throw an exception.
  """
  assert swarming_task_output

  if swarming_task_output.iterations > 0:
    return (float(swarming_task_output.pass_count) /
            swarming_task_output.iterations)

  # If there are no errors and no iterations ran, the test does not exist.
  return flake_constants.PASS_RATE_TEST_NOT_FOUND


def HasPassRateConverged(overall_pass_rate,
                         total_iterations,
                         partial_pass_rate,
                         partial_iterations,
                         margin=flake_constants.CONVERGENCE_PERCENT):
  """Determines if a pass rate has converged to within a margin.

  Args:
    overall_pass_rate (float): Overall pass rate with the partial pass rate
        factored in.
    total_iterations (int): Overall number of iterations ran with the partial
        iterations factored in.
    partial_pass_rate (float): A subset of the pass rate to test if the overall
        pass rate has converged. Should be from the most recent sampling.
    partial_iterations (int): A subset of all iterations to test if the overall
        pass rate has converged. Should be from the most recent sampling.
    margin (float): The margin to determine convergence.

  Returns:
    True if the overall pass rate with vs without the most recent sampling is
        within the specified margin.
  """
  if not total_iterations:
    return False

  # Nonexistent tests are not supported and should be checked for before
  # using this function.
  assert overall_pass_rate >= 0 and overall_pass_rate <= 1.0
  assert partial_pass_rate >= 0 and partial_pass_rate <= 1.0
  assert partial_iterations <= total_iterations

  # Determine the pass rate with vs without partial_pass_count and
  # partial_iterations. If the change change with vs without is within the
  # specified margin, then the pass rates are converged.
  overall_pass_count = int(round(overall_pass_rate * total_iterations))
  partial_pass_count = int(round(partial_pass_rate * partial_iterations))
  pass_rate_without_partials = (
      float(overall_pass_count - partial_pass_count) /
      (total_iterations - partial_iterations))

  return abs(pass_rate_without_partials - overall_pass_rate) <= margin


def HasSufficientInformation(overall_pass_rate, total_iterations,
                             partial_pass_rate, partial_iterations):
  """Determines whether a pass rate is enough for an analysis to proceed.

  Args:
    overall_pass_rate (float): Overall pass rate with the partial pass rate
        factored in.
    total_iterations (int): Overall number of iterations ran with the partial
        iterations factored in.
    partial_pass_rate (float): A subset of the pass rate to test if the overall
        pass rate has converged. Should be from the most recent sampling.
    partial_iterations (int): A subset of all iterations to test if the overall
        pass rate has converged. Should be from the most recent sampling.

  Returns:
    Whether the overall pass rate with number of iterations is sufficient to
        proceed.
  """
  flake_settings = waterfall_config.GetCheckFlakeSettings()
  lower_flake_threshold = flake_settings.get(
      'lower_flake_threshold', flake_constants.DEFAULT_LOWER_FLAKE_THRESHOLD)
  upper_flake_threshold = flake_settings.get(
      'upper_flake_threshold', flake_constants.DEFAULT_UPPER_FLAKE_THRESHOLD)
  minimum_iterations = waterfall_config.GetCheckFlakeSettings().get(
      'minimum_iterations_required_for_confergence',
      flake_constants.MINIMUM_ITERATIONS_REQUIRED_FOR_CONVERGENCE)

  if overall_pass_rate is None or total_iterations == 0:
    return False

  if MinimumIterationsReached(total_iterations):
    # The test is already flaky beyond reasonable doubt.
    if not IsStable(overall_pass_rate, lower_flake_threshold,
                    upper_flake_threshold):
      return True

    # The test is stable thus far. Check for convergence.
    return HasPassRateConverged(overall_pass_rate, total_iterations,
                                partial_pass_rate, partial_iterations)

  # For cases with few iterations, check if the test is flaky or stable by
  # checking its theoretical pass rate padded up to the minimum required
  # iterations with both passes and fails. Only if it is flaky with both
  # theoretical values can it safely be deemed flaky.
  overall_pass_count = float(overall_pass_rate * total_iterations)
  theoretical_minimum_pass_rate = overall_pass_count / minimum_iterations
  theoretical_maximum_pass_rate = ((
      overall_pass_count + minimum_iterations - total_iterations) /
                                   minimum_iterations)

  return (not IsStable(theoretical_minimum_pass_rate, lower_flake_threshold,
                       upper_flake_threshold) and
          not IsStable(theoretical_maximum_pass_rate, lower_flake_threshold,
                       upper_flake_threshold))


def IsFullyStable(pass_rate):
  """Determines whether a pass rate is fully stable.

      Fully stable data points have pass rates that are -1 (nonexistent
      test), 0%, or 100%.

  Args:
    pass_rate (float): A data point's pass rate.

  Returns:
    Boolean whether the pass rate is fully stable, which disallows tolerances
        in the analysis' lower/upper flake thresholds.
  """
  assert pass_rate is not None
  return IsStable(pass_rate, 0, 1.0)


def IsStableDefaultThresholds(pass_rate):
  """Override for IsStable that uses the default thresholds."""
  flake_settings = waterfall_config.GetCheckFlakeSettings()
  lower_flake_threshold = flake_settings.get(
      'lower_flake_threshold', flake_constants.DEFAULT_LOWER_FLAKE_THRESHOLD)
  upper_flake_threshold = flake_settings.get(
      'upper_flake_threshold', flake_constants.DEFAULT_UPPER_FLAKE_THRESHOLD)
  return IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold)


def IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold):
  """Determines whether a pass rate is stable, with tolerances.

    Flake Analyzer should allow for a slight tolerance when determining a test
    is flaky or stable, for example 98% passing or above and 2% or below are
    still considered stable. If this tolerance is not to be used, use
    IsFullyStable instead which ensures 100% and 0% as the thresholds.

  Args:
    pass_rate (float): A floating point value between 0 and 1 to check whether
        it is within tolerable bounds.
    lower_flake_threshold (float): The lower bound value a pass rate must be
        under to be considered stable. Should be between 0 and 1.
    upper_flake_threshold (float): the upper bound value a pass rate must be
        over in order to be considered stable. Shoul be between 0 and 1 and
        greater than upper_flake_threshold.
  """
  assert upper_flake_threshold > lower_flake_threshold
  return (TestDoesNotExist(pass_rate) or
          pass_rate < lower_flake_threshold + flake_constants.EPSILON or
          pass_rate > upper_flake_threshold - flake_constants.EPSILON)


def MinimumIterationsReached(iterations):
  """Determines if a minimum number of iterations has been met.

  Args:
    iterations (int): The number of iterations a data point already ran.

  Returns:
    True if the data point has at least a minimum number of iterations.
  """
  minimum_iterations = waterfall_config.GetCheckFlakeSettings().get(
      'minimum_iterations_required_for_confergence',
      flake_constants.MINIMUM_ITERATIONS_REQUIRED_FOR_CONVERGENCE)

  return iterations >= minimum_iterations


def TestDoesNotExist(pass_rate):
  """Determines whether a pass_rate represents a nonexistent test."""
  return (pass_rate >=
          (flake_constants.PASS_RATE_TEST_NOT_FOUND - flake_constants.EPSILON)
          and pass_rate <=
          (flake_constants.PASS_RATE_TEST_NOT_FOUND + flake_constants.EPSILON))
