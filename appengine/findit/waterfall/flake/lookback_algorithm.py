# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class NormalizedDataPoint(object):

  def __init__(self, run_point_number, pass_rate, has_valid_artifact=True):
    self.run_point_number = run_point_number
    self.pass_rate = pass_rate
    self.has_valid_artifact = has_valid_artifact


def IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold):
  return pass_rate < lower_flake_threshold or pass_rate > upper_flake_threshold


def _TestDoesNotExist(pass_rate):
  return pass_rate < 0


def GetCategorizedDataPoints(data_points):
  valid_points = []
  invalid_points = []
  for data_point in data_points:
    if data_point.has_valid_artifact:
      valid_points.append(data_point)
    else:
      invalid_points.append(data_point)

  return valid_points, invalid_points


def _FindNeighbor(invalid_run_point, all_builds):
  """Looks for a neighbor to replace or stop the analysis.

  Args:
    invalid_run_point (int): The build number with invalid artifact.
    all_builds (list): A list of build numbers that have been checked.

  Returns: New build to check.
  """
  return (invalid_run_point - 1 if invalid_run_point + 1 in all_builds else
          invalid_run_point + 1)


def _SequentialSearch(
    analyzed_points, lower_boundary_index, all_builds, invalid_builds):
  """Determines the next run number for sequential search, or the culprit.

      Should only be called by _ExponentialSearch when sequential search
      is ready.

  Args:
    analyzed_points (list): A list of already-computed data points to analyze
        whether sequential search is done or needs to continue.
    lower_boundary_index (int): The index in |data_list| to check whether
        sequential search is already done.
    all_builds (list): A list of build numbers that have been checked.
    invalid_builds (list): A list of build numbers that cannot be used because
        the build artifact is invalid.

  Returns:
    next_run_point (int): The next run point in sequential search. Will be None
        if suspected_culprit is returned.
    suspected_culprit (int): The suspected culprit, if any. Will be None if
        next_run_point is needed.
    iterations_to_rerun (int): None. Used only for return purposes by the
        calling function.
  """

  lower_boundary = analyzed_points[lower_boundary_index].run_point_number
  run_after_lower_boundary = (
      analyzed_points[lower_boundary_index - 1].run_point_number)
  if run_after_lower_boundary == lower_boundary + 1:
    # Sequential search is done, return culprit.
    return None, run_after_lower_boundary, None

  next_run_point = lower_boundary + 1
  result = None

  while next_run_point in invalid_builds:
    next_run_point = _FindNeighbor(next_run_point, all_builds)

  if next_run_point in all_builds:
    # next_run_point is valid and the result should be stable (if flaky, this
    # function should have returned earlier). The build next to it should be
    # the suspect.
    result = next_run_point + 1
    next_run_point = None

  return next_run_point, result, None


def _ExponentialSearch(data_points,
                       algorithm_settings,
                       lower_bound_run_point_number=None):
  """Determines the next numerical point to check flakiness on.

  Args:
    data_points (list): A list of normalized data points of already-completed
        tasks (swarming or try job). A normalized has only pass_rate and
        run_point_number.
    algorithm_settings (dict): A dict of parameters for lookback algorithm.
    lower_bound_run_point_number (int): An optional int lower boundary run point
        not to exceed.

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
  max_dive_in_a_row = algorithm_settings.get('max_dive_in_a_row', 0)
  dive_rate_threshold = algorithm_settings.get('dive_rate_threshold')

  flakes_in_a_row = 0
  dives_in_a_row = 0
  next_run_point = None

  valid_points, invalid_points = GetCategorizedDataPoints(data_points)
  # Gets all builds with invalid artifacts, this should be empty for try jobs.
  invalid_builds = [ip.run_point_number for ip in invalid_points]
  all_builds = [dp.run_point_number for dp in data_points]

  number_of_valid_points = len(valid_points)

  for i in xrange(number_of_valid_points):
    pass_rate = valid_points[i].pass_rate
    run_point_number = valid_points[i].run_point_number

    if _TestDoesNotExist(pass_rate):
      if flakes_in_a_row:
        return _SequentialSearch(valid_points, i, all_builds, invalid_points)
      else:
        # No flaky region has been identified, no findings.
        return None, None, None

    elif IsStable(pass_rate, lower_flake_threshold, upper_flake_threshold):

      # If the swarming rerun for the first build had stable results, either
      # the test is really stable so we should bail out or
      # the number of iterations is not high enough so we should increase
      # the number and rerun.
      iterations_to_rerun = algorithm_settings.get('iterations_to_rerun')
      max_iterations_to_rerun = algorithm_settings.get(
          'max_iterations_to_rerun', 100)

      iterations_to_rerun *= 2
      if iterations_to_rerun > max_iterations_to_rerun:
        # Cannot increase iterations_to_rerun, need to make a decision.
        if flakes_in_a_row:  # Ready for sequential search.
          return _SequentialSearch(valid_points, i, all_builds, invalid_builds)
        else:  # First build is stable, bail out.
          return None, None, None

      # Rerun the same build with a higher number of iterations.
      return run_point_number, None, iterations_to_rerun

    else:  # Flaky result.
      flakes_in_a_row += 1

      if run_point_number == lower_bound_run_point_number:  # pragma: no branch
        # The earliest commit_position to look back is already flaky. This is
        # the culprit.
        return None, run_point_number, None

      if max_dive_in_a_row:
        # Check for dives. A dive is a sudden drop in pass rate.
        # Check the pass_rate of previous run, if this is the first data_point,
        # consider the virtual previous run is stable.
        previous_pass_rate = valid_points[i - 1].pass_rate if i > 0 else 0

        if IsStable(
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
        return _SequentialSearch(
            valid_points, i - dives_in_a_row + 1, all_builds, invalid_builds)
      else:
        step_size = flakes_in_a_row
        next_run_point = run_point_number - step_size

  next_run_point = (
      next_run_point if next_run_point >= lower_bound_run_point_number else
      lower_bound_run_point_number)
  result = None

  while next_run_point in invalid_builds:
    next_run_point = _FindNeighbor(next_run_point, all_builds)

  return next_run_point, result, None


def BisectPoint(lower_bound, upper_bound):
  assert upper_bound >= 0
  assert lower_bound >= 0
  assert upper_bound >= lower_bound
  return lower_bound + (upper_bound - lower_bound) / 2


def _GetBisectRange(data_points, algorithm_settings):
  """Gets the latest lower/upper bounds to bisect.

  Args:
    data_points (list): A list of data points within a range sorted in ascending
        order by run_point_number.
    algorithm_settings (dict): The parameter settings used for analysis to help
        determine a flaky vs stable data point.

  Returns:
    lower_bound (int), upper_bound (int): The run number of the latest stable
        data_point and run number of the earliest subsequent flaky data point.
  """
  assert len(data_points) >= 2
  lower_flake_threshold = algorithm_settings.get('lower_flake_threshold')
  upper_flake_threshold = algorithm_settings.get('upper_flake_threshold')
  assert not IsStable(
      data_points[-1].pass_rate, lower_flake_threshold, upper_flake_threshold)

  latest_stable_index = 0
  for i, data_point in enumerate(data_points):
    if IsStable(
        data_point.pass_rate, lower_flake_threshold, upper_flake_threshold):
      latest_stable_index = i

  return (data_points[latest_stable_index].run_point_number,
          data_points[latest_stable_index + 1].run_point_number)


def _Bisect(data_points, algorithm_settings):
  """Bisects a regression range or returns a culprit.

  Args:
    data_points (list): A list of data points sorted in ascending order by
        run point number expected to contain at least one stable point
        followed by a flaky point somewhere later in the list.
    algorithm_settings (dict): The pramaters used during analysis.

  Returns:
    (int, int): The next point to run and suspected run point number. If the
        next run number is determined, there will be no suspected point and vice
        versa.
  """
  lower_bound, upper_bound = _GetBisectRange(data_points, algorithm_settings)
  next_run_point = BisectPoint(lower_bound, upper_bound)

  if next_run_point == lower_bound:
    return None, upper_bound

  return next_run_point, None


def _ShouldRunBisect(lower_bound_run_point_number,
                     upper_bound_run_point_number):
  """Determines whether or not bisect should be run."""
  return (lower_bound_run_point_number is not None and
          upper_bound_run_point_number is not None)


def GetNextRunPointNumber(data_points,
                          algorithm_settings,
                          lower_bound_run_point_number=None,
                          upper_bound_run_point_number=None):
  """Determines the next point to analyze to be handled by the caller."""
  if _ShouldRunBisect(lower_bound_run_point_number,
                      upper_bound_run_point_number):
    next_run_point, suspected_point = _Bisect(data_points, algorithm_settings)
    return next_run_point, suspected_point, None

  return _ExponentialSearch(
      data_points, algorithm_settings, lower_bound_run_point_number)
