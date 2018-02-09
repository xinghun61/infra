# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions for processing a flaky test's pass rates."""

from waterfall import waterfall_config
from waterfall.flake import flake_constants


def ArePassRatesEqual(pass_rate_1, pass_rate_2):
  assert pass_rate_1 is not None
  assert pass_rate_2 is not None
  return abs(pass_rate_1 - pass_rate_2) <= flake_constants.EPSILON


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
  """Determines a pass rate based on a swarming task's output."""
  assert swarming_task_output

  if swarming_task_output.error:
    # TODO(crbug.com/808947): A failed swarming task's partial data can
    # sometimes still be salvaged.
    return None

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


def HasSufficientInformationForConvergence(
    overall_pass_rate, total_iterations, partial_pass_rate, partial_iterations):
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
  return (MinimumIterationsReached(total_iterations) and
          HasPassRateConverged(overall_pass_rate, total_iterations,
                               partial_pass_rate, partial_iterations))


def IsFullyStable(pass_rate):
  """Determines whether a pass rate is fully stable.

      Fully stable data points have pass rates that are either -1 (nonexistent)
      test, 0%, or 100%.

  Args:
    pass_rate (float): A data point's pass rate.

  Returns:
    Boolean whether the pass rate is fully stable, which disallows tolerances
        in the analysis' lower/upper flake thresholds.
  """
  assert pass_rate is not None
  return (TestDoesNotExist(pass_rate) or pass_rate <= flake_constants.EPSILON or
          abs(pass_rate - 1.0) <= flake_constants.EPSILON)


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
