# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

# Maximum number of versions to look back.
_MAXIMUM_WINDOW_SIZE = 30

# Add epsilon to avoid dividing by zero when computing spike score.
_EPSILON = 0.00000001

# Default value to control weight of current data when computing spike score.
_DEFAULT_ALPHA = 0.9

# Threshold of spike score.
_SPIKENESS_THRESHOLD = 20


# TODO(http://crbug.com/644406): This code needs cleaning/refactoring 
def GetSpikeIndexes(data_series, alpha=_DEFAULT_ALPHA,
                    threshold=_SPIKENESS_THRESHOLD):
  """Given a time series, determine anomolous spikes.
  
  The time series is represented by a list of (x,y) tuples, where the
  position of the tuple in the list is the time at which the event
  occured, x is an abstract name for that time, and y is the value of
  the time series at that point in time. We detect spikes by determining
  when the time series diverges too much from the running average (of
  the y values). The alpha parameter determines how readily we update
  the running average; which is to say, how much weight we give each
  new event compared to the weight we give to the current running
  average. The threshold parameter defines when we've deviated 'too far'
  from the running average, and therefore say that this event is in fact
  a spike.

  Args:
    data_series (list): A list of (x, y) tuples where y is a number.
    alpha (float): In (0, 1], it controls the weight of current data
      when computing the running mean, a higher value has more weight.
    threshold (float): Threshold for when something counts as a spike.

  Returns:
    A list of spike indexes (i.e., positions in the data_series list;
    not the abstract names associated with those indices)
  """
  spike_indexes = []

  if not data_series or len(data_series) == 1:
    return spike_indexes

  logging.info('For data series %s', repr(data_series))
  logging.info('Threshold is %f', threshold)

  previous_mean = data_series[0][1]
  for i, (_, y) in enumerate(data_series[1:]):
    current_mean = (1 - alpha) * previous_mean + alpha * y

    # Spike score is basically relative increase. Add epsilon
    # to both numerator and denominator to avoid dividing by zero error.
    spike_score = ((current_mean - previous_mean + _EPSILON) /
                   (previous_mean + _EPSILON))
    logging.info('The spike score for data %s is %s',
                 repr(data_series[i]), spike_score)
    if spike_score > threshold:
      spike_indexes.append(i + 1)

    previous_mean = current_mean

  return spike_indexes


def GetRegressionRangeFromSpike(spike_index, versions):
  """Get the regression range based on spike_index and versions."""
  if spike_index < 1 or spike_index >= len(versions):
    return None

  return (versions[spike_index - 1], versions[spike_index])


def GetAttributesListFromHistoricData(historic_metadata, attributes):
  """Returns a list of attributes from historic_metadata.

  Args:
    historic_metadata (list): A list of dict of metadata, for example:
      [{'chrome_version': '1', 'cpm': 0}, {'chrome_version': '2', 'cpm': 0}]
    attributes (list): A list of attribute names.

  Returns:
    A list of strs(attributes has only 1 element), or tuples
  """
  if not attributes:
    return []

  attributes_list = []

  for data in historic_metadata:
    attributes_entry = []

    for attribute in attributes:
      attributes_entry.append(data[attribute])

    if len(attributes_entry) == 1:
      attributes_list.append(attributes_entry[0])
    else:
      attributes_list.append(tuple(attributes_entry))

  return attributes_list


def DetectRegressionRange(historic_metadata, max_win_size=_MAXIMUM_WINDOW_SIZE):
  """Detect regression range from historic_metadata data.

  Args:
    historic_metadata (list): A list of dict of metadata, the list is sorted by
      'chrome_version' from oldest to latest.
      For example:
      [{'chrome_version': '1', 'cpm': 0}, {'chrome_version': '2', 'cpm': 0}]
    max_win_size (int): Number of versions to look back from
      the currect version.

  Returns:
    A tuple, (last_good_version, first_bad_version) or None if none found.
  """
  if not historic_metadata:
    return None

  # Truncate the historic data so we only analyze data for max_win_size of
  # latest versions.
  versions_to_cpm = GetAttributesListFromHistoricData(
      historic_metadata[-max_win_size:], ['chrome_version', 'cpm'])

  versions, _ = zip(*versions_to_cpm)
  spike_indexes = GetSpikeIndexes(versions_to_cpm)

  if not spike_indexes:
    logging.warning('Failed to find spikes in history data %s' % repr(
        historic_metadata))
    return None

  # Only return the latest regression range.
  return GetRegressionRangeFromSpike(spike_indexes[-1], versions)
