# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


_DEFAULT_MAX_ITERATIONS_TO_RERUN = 500
_DEFAULT_ITERATION_INCREASE_STEP_SIZE = 100


class NormalizedDataPoint():

  def __init__(self, run_point_number, pass_rate):
    self.run_point_number = run_point_number
    self.pass_rate = pass_rate


def _IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold):
  return pass_rate < lower_flake_threshold or pass_rate > upper_flake_threshold


def _TestDoesNotExist(pass_rate):
  return pass_rate < 0


def _SequentialSearch(data_points, lower_boundary_index):
  """Determines the next run number for sequential search, or the culprit.

      Should only be called by GetNextRunPointNumber when sequential search
      is ready.

  Args:
    data_points (list): A list of already-computed data points to analyze
        whether sequential search is done or needs to continue.
    lower_boundary_index (int): The index in |data_list| to check whether
        sequential search is already done.

  Returns:
    next_run_point (int): The next run point in sequential search. Will be None
        if suspected_culprit is returned.
    suspected_culprit (int): The suspected culprit, if any. Will be None if
        next_run_point is needed.
    iterations_to_rerun (int): None. Used only for return purposes by the
        calling function.
  """
  lower_boundary = data_points[lower_boundary_index].run_point_number
  run_after_lower_boundary = (
      data_points[lower_boundary_index - 1].run_point_number)

  if run_after_lower_boundary == lower_boundary + 1:
    # Sequential search is done, return culprit.
    return None, run_after_lower_boundary, None

  return lower_boundary + 1, None, None


def GetNextRunPointNumber(data_points, algorithm_settings,
                          lower_bound_run_point_number=None):
  """Determines the next numerical point to check flakiness on.

  Args:
    data_points (list): A list of normalized data points of already-completed
        tasks (swarming or try job). A normalized has only pass_rate and
        run_point_number.
    algorithm_settings (dict): A dict of parameters for lookback algorithm.
    lower_boundary_run_point_number (int): An optional int lower boundary run
        point not to exceed.

  Returns:
    (next_run_point, suspected_point, iterations_to_rerun): The next point to
        check, suspected point that the flakiness was introduced in and
        iterations to run following swarming tasks if changed.
        If next_run_point needs to be checked, returns
        (next_run_point, None, iterations_to_rerun or None).
        If a suspected point is found, returns
        (None, suspected_point, None).
        If ultimately no findings, returns
        (None, None, None).
  """
  # A description of this algorithm can be found at:
  # https://docs.google.com/document/d/1wPYFZ5OT998Yn7O8wGDOhgfcQ98mknoX13AesJaS6ig/edit
  lower_flake_threshold = algorithm_settings.get('lower_flake_threshold')
  upper_flake_threshold = algorithm_settings.get('upper_flake_threshold')
  max_stable_in_a_row = algorithm_settings.get('max_stable_in_a_row')
  max_flake_in_a_row = algorithm_settings.get('max_flake_in_a_row')
  max_dive_in_a_row = algorithm_settings.get('max_dive_in_a_row', 0)
  dive_rate_threshold = algorithm_settings.get('dive_rate_threshold')

  stables_in_a_row = 0
  flakes_in_a_row = 0
  dives_in_a_row = 0
  stables_happened = False
  flakes_first = 0
  flaked_out = False
  next_run_point = None
  number_of_data_points = len(data_points)

  for i in xrange(number_of_data_points):
    pass_rate = data_points[i].pass_rate
    run_point_number = data_points[i].run_point_number

    if _TestDoesNotExist(pass_rate):
      if flaked_out or flakes_first:
        # Flaky region found, ready for sequential search.
        return _SequentialSearch(data_points, i - stables_in_a_row)
      else:
        # No flaky region has been identified, no findings.
        return None, None, None

    elif _IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold):
      stables_in_a_row += 1
      flakes_in_a_row = 0
      dives_in_a_row = 0
      stables_happened = True

      if number_of_data_points == 1:
        # If the swarming rerun for the first build had stable results, either
        # the test is actually stable and we should bail out, or the number of
        # iterations is not high enough and we should rerun with a higher value.
        iterations_to_rerun = algorithm_settings.get('iterations_to_rerun')
        max_iterations_to_rerun = algorithm_settings.get(
            'max_iterations_to_rerun')

        iterations_to_rerun *= 2
        if iterations_to_rerun > max_iterations_to_rerun:
          # Conside this as stabled-out and no flake region, so no findings.
          return None, None, None

        # Rerun the same build with a higher number of iterations.
        return run_point_number, None, iterations_to_rerun

      if stables_in_a_row <= max_stable_in_a_row:
        # No stable region yet, keep searching.
        # TODO(http://crbug.com/670888): Pin point a stable point rather than
        # looking for stable region further narrow down the sequential search
        # range further.
        next_run_point = run_point_number - 1
        continue

      # Flake region is also found, ready for sequential search.
      return _SequentialSearch(data_points, i - stables_in_a_row + 1)

    else:  # Flaky result.
      if i < number_of_data_points - 1:
        # Check if the test was newly added at this run point number and is
        # already flaky.
        next_data_point = data_points[i + 1]

        if (run_point_number - next_data_point.run_point_number == 1 and
            next_data_point.pass_rate == -1):
          # Flakiness was introduced in this run number.
          return None, run_point_number, None

      flakes_in_a_row += 1
      stables_in_a_row = 0

      if flakes_in_a_row > max_flake_in_a_row:  # Identified a flaky region.
        flaked_out = True

      if not stables_happened:
        # No stables yet.
        flakes_first += 1

      if run_point_number == lower_bound_run_point_number:  # pragma: no branch
        # The earliest commit_position to look back is already flaky. This is
        # the culprit.
        return None, run_point_number, None

      if max_dive_in_a_row:
        # Check for dives. A dive is a sudden drop in pass rate.
        # Check the pass_rate of previous run, if this is the first data_point,
        # consider the virtual previous run is stable.
        previous_pass_rate = data_points[i - 1].pass_rate if i > 0 else 0

        if _IsStable(
            previous_pass_rate, lower_flake_threshold, upper_flake_threshold):
          next_run_point = run_point_number - flakes_in_a_row
          continue

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
          next_run_point = run_point_number - step_size
          continue

        # Dived out.
        # Flake region must have been found, ready for sequential search.
        return _SequentialSearch(data_points, i - dives_in_a_row + 1)
      else:
        step_size = flakes_in_a_row
        next_run_point = run_point_number - step_size

  if next_run_point < lower_bound_run_point_number:
    return lower_bound_run_point_number, None, None

  return next_run_point, None, None
