# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from perf_dashboard import find_step


def _Steppiness(data_points, index_picker, split_index_value):
  """Calculates and returns the steppiness of the data points.

  Args:
    data_points (list): A list of master_flake_analysis.DataPoint instances.
    index_picker (function): A function to return the value of the index field
      given a master_flake_analysis.DataPoint instance as input.
    split_index_value (object): The value at which to split the data points.
  """
  sorted_data = sorted(data_points, key=index_picker)
  split_index = None
  for i, datum in enumerate(sorted_data):
    if index_picker(datum) == split_index_value:
      split_index = i
      break
  assert split_index is not None, (
      '%r not in the given data list' % split_index_value)
  values = [d.pass_rate for d in sorted_data]

  if sorted_data[0].pass_rate < 0:
    # Fill in data points before a new test exists.
    padding = [1, 1, 1]
    values = padding + map(abs, values)
    split_index += len(padding)

  if len(values) < 5:  # Without enough data, the result is unreliable.
    return 0

  return find_step.Steppiness(values, split_index)


def SteppinessForBuild(data_points, build_number):
  """Returns the steppiness for the data points split by the build number.

  Args:
    data_points (list): A list of master_flake_analysis.DataPoint instances.
    build_number (int): The build number to split the data points.
  """
  data_points = filter(lambda x: x.try_job_url is None, data_points)
  return _Steppiness(data_points, lambda dp: dp.build_number, build_number)


def SteppinessForCommitPosition(data_points, commit_position):
  """Returns the steppiness for the data points split by the build number.

  Args:
    data_points (list): A list of master_flake_analysis.DataPoint instances.
    commit_position (int): The commit position to split the data points.
  """
  return _Steppiness(data_points, lambda dp: dp.commit_position,
                     commit_position)
