# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

# Default value for the maximum number of versions to look back.
_MAXIMUM_WINDOW_SIZE = 30

# Add epsilon to avoid dividing by zero when computing spikiness.
_EPSILON = 0.00000001

# Default value to control weight of current data when computing spikiness.
_DEFAULT_ALPHA = 0.9

# Threshold for calling something a spike.
_SPIKINESS_THRESHOLD = 20


# TODO(wrengr): make this streaming, rather than holding onto the whole list.
def GetSpikes(events, get_value, alpha=_DEFAULT_ALPHA,
              threshold=_SPIKINESS_THRESHOLD):
  """Given a time series, detect regression ranges for anomalous spikes.

  The time series is represented by a list of "events" together with
  a function for computing the "value" of each event. We assume the
  events are given in order, and the only thing we care about them is
  their value. As we scan through the list, if we notice any "spikes" in
  the course of values (i.e., the current value seems anomalous compared
  to the values we've seen previously), then we produce a tuple of the
  events bracketing the spike. Since there can be many spikes, we return
  a list of these tuples.

  The model we use for detecting spikes is exponential smoothing. This
  model is based on the running average of the events' values, and it has
  two parameters: the alpha parameter determines how readily we update
  the running average each time we see a new event, and the threshold
  parameter determines when an event's value deviates far enough from the
  running average that we call it a spike. N.B., in time series analysis
  more generally, exponential smoothing is considered a naive model since
  it cannot account for things like scaling (i.e., if we multiply all
  the values by some constant, then we'll need to adjust the threshold
  by that constant too) and noise (i.e., if we add noise to the values,
  then we'll need to adjust the threshold to try and filter that noise
  out). However, based on some preliminary tests, this naive model seems
  to be good enough for our particular task.

  Args:
    events (list): A list of objects representing "events" in a time
      series. The events themselves can be any sort of object (including
      None), all we care about is their value according to get_value. We
      assume the events are already in order, but we do not care about
      their exact position within the list.
    get_value (callable): a valuation function mapping events to numbers.
    alpha (float): In (0, 1], controls how we balance between evidence
      from new events vs the running average. When alpha=0 we completely
      ignore the new event; when alpha=1 we completely ignore the running
      average.
    threshold (float): How far away from the running average something
      can be before we consider it a spike.

  Returns:
    A list of event pairs, each of which denotes the regression range
    for a spike. That is, for each pair, the first component is the
    event just before the spike, and the second component is the event
    just after the spike. Thus, the pairs are always of events which
    were adjacent in the event list. If the event list has fewer than
    two elements, then we return the empty list (rather than returning
    None or throwing an exception).
  """
  # TODO(wrengr): Is there a way to raise a more helpful error whenever
  # get_value is not callable? The default error is totally correct for
  # tracking down the bug, but it may not be what the end user wants to see.

  # TODO(wrengr): would it be better to return None so callers fail fast?
  if not events or len(events) == 1:
    return []

  logging.info('For data series %s', repr(events))
  logging.info('Alpha is %f', alpha)
  logging.info('Threshold is %f', threshold)

  # TODO(wrengr): do we care enough about precision to avoid the floating
  # point issues of computing the mean in the naive/straightforward way?
  spikes = []
  previous_event = events[0]
  previous_mean = get_value(previous_event)
  for event in events[1:]:
    current_value = get_value(event)
    current_mean = (1 - alpha) * previous_mean + alpha * current_value

    # Spikiness is basically relative increase. Add epsilon to both
    # numerator and denominator to avoid dividing by zero error.
    spikiness = ((current_mean - previous_mean + _EPSILON) /
                 (previous_mean + _EPSILON))
    logging.info('The spikiness of event %s is %s', repr(event), spikiness)
    if spikiness > threshold:
      spikes.append((previous_event, event))

    previous_event = event
    previous_mean = current_mean

  return spikes


def DetectRegressionRange(historic_metadata, max_win_size=_MAXIMUM_WINDOW_SIZE):
  """Detect regression range from historic_metadata data.

  Args:
    historic_metadata (list): A list of dict of metadata, the list is
      sorted by 'chrome_version' from oldest to latest. For example:
      [{'chrome_version': '1', 'cpm': 0}, {'chrome_version': '2', 'cpm': 0}]
    max_win_size (int): Number of versions to look back from the current
      version.

  Returns:
    A tuple, (last_good_version, first_bad_version) or None if none found.
  """
  if not historic_metadata:
    return None

  # Truncate the historic data so we only analyze data for max_win_size of
  # latest versions.
  spikes = GetSpikes(historic_metadata[-max_win_size:], lambda x: x['cpm'])

  if not spikes:
    logging.warning('Failed to find spikes in history data %s' % repr(
        historic_metadata))
    return None

  # Only return the last/most-recent regression range.
  last_good, first_bad = spikes[-1]
  return last_good['chrome_version'], first_bad['chrome_version']
