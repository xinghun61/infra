# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class NormalizedDataPoint():

  def __init__(self, run_point_number, pass_rate):
    self.run_point_number = run_point_number
    self.pass_rate = pass_rate


def _IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold):
  return pass_rate < lower_flake_threshold or pass_rate > upper_flake_threshold


def _TestDoesNotExist(pass_rate):
  return pass_rate < 0


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
    (next_run_point, suspected_point): The next point to check and suspected
        point that the flakiness was introduced in. If next_run_point needs to
        be checked, returns (next_run_point, None). If a suspected point is
        found, returns (None, suspected_point). If ultimately no findings,
        returns (None, None).
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

  for i in xrange(len(data_points)):
    pass_rate = data_points[i].pass_rate
    run_point_number = data_points[i].run_point_number

    if _TestDoesNotExist(pass_rate):
      if flaked_out or flakes_first:
        lower_boundary = data_points[i - stables_in_a_row].run_point_number
        return lower_boundary + 1, None
      else:
        # No flaky region has been identified, no findings.
        return None, None
    elif _IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold):
      stables_in_a_row += 1
      flakes_in_a_row = 0
      dives_in_a_row = 0
      stables_happened = True

      if stables_in_a_row <= max_stable_in_a_row:
        # No stable region yet, keep searching.
        # TODO(http://crbug.com/670888): Pin point a stable point rather than
        # looking for stable region further narrow down the sequential search
        # range further.
        next_run_point = run_point_number - 1
        continue

      # Stable region found.
      if not flaked_out and not flakes_first:
        # Already stabled-out but no flake region yet, no findings.
        return None, None

      # Flake region is also found, ready for sequential search.
      lower_boundary_index = i - stables_in_a_row + 1
      lower_boundary = data_points[lower_boundary_index].run_point_number
      previous_run_point = data_points[
          lower_boundary_index - 1].run_point_number

      if previous_run_point == lower_boundary + 1:
        # Sequential search is done.
        return None, previous_run_point

      # Continue sequential search.
      return lower_boundary + 1, None
    else:
      # Flaky result.
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
        return None, run_point_number

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
        lower_boundary_index = i - dives_in_a_row + 1
        lower_boundary = data_points[lower_boundary_index].run_point_number
        build_after_lower_boundary = (
            data_points[lower_boundary_index - 1].run_point_number)

        if build_after_lower_boundary == lower_boundary + 1:
          # Sequential search is done.
          return None, build_after_lower_boundary
        # Continue sequential search.
        return lower_boundary + 1, None
      else:
        step_size = flakes_in_a_row
        next_run_point = run_point_number - step_size

  if next_run_point < lower_bound_run_point_number:
    return lower_bound_run_point_number, None

  return next_run_point, None
