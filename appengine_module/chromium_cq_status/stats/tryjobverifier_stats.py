# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from appengine_module.chromium_cq_status.shared.config import TRYJOBVERIFIER
from appengine_module.chromium_cq_status.stats.analyzer import (
  AnalyzerGroup,
  CountAnalyzer,
  ListAnalyzer,
)

counted_actions = (
  ('error', 'Number of tryjob verifier runs errored.'),
  ('fail', 'Number of tryjob verifier runs failed.'),
  ('pass', 'Number of tryjob verifier runs passed.'),
  ('retry', 'Number of tryjob verifier runs retried.'),
  ('skip', 'Number of tryjob verifier runs skipped.'),
  ('start', 'Number of tryjob verifier runs started.'),
  ('timeout', 'Number of tryjob verifier runs that timed out.'),
)

tryjobverifier_terminator_actions = (
  'verifier_pass',
  'verifier_fail',
  'verifier_retry',
  'verifier_timeout',
)


class TryjobverifierAnalyzer(AnalyzerGroup):  # pragma: no cover
  def __init__(self):
    super(TryjobverifierAnalyzer, self).__init__(
      TryjobverifierActionCountGroup,
      TryjobverifierFirstRunDurations,
      TryjobverifierRetryDurations,
      TryjobverifierTotalDurations,
    )


class TryjobverifierActionCount(CountAnalyzer):  # pragma: no cover
  def __init__(self, action, description):
    super(TryjobverifierActionCount, self).__init__()
    self.action = action
    self.description = description

  def new_attempts(self, attempts, reference):
    self.tally[reference] += count_actions(attempts, 'verifier_' + self.action)

  def _get_name(self):
    return 'tryjobverifier-%s-count' % self.action


class TryjobverifierActionCountGroup(AnalyzerGroup):  # pragma: no cover
  def __init__(self):
    self.analyzers = []
    for action, description in counted_actions:
      self.analyzers.append(TryjobverifierActionCount(action, description))


class TryjobverifierFirstRunDurations(ListAnalyzer):  # pragma: no cover
  description = 'Time spent on each tryjob verifier first run.'
  unit = 'seconds'
  def new_attempts(self, attempts, reference):
    for attempt in attempts:
      start_timestamp = None
      end_timestamp = None
      for record in attempt:
        if record.fields.get('verifier') != TRYJOBVERIFIER:
          continue
        if record.fields.get('action') == 'verifier_start':
          start_timestamp = record.timestamp
        if record.fields.get('action') in tryjobverifier_terminator_actions:
          end_timestamp = record.timestamp
          break
      if start_timestamp and end_timestamp:
        duration = (end_timestamp - start_timestamp).total_seconds()
        self.points.append((duration, reference))


class TryjobverifierRetryDurations(ListAnalyzer):  # pragma: no cover
  description = 'Time spent on each tryjob verifier retry.'
  unit = 'seconds'
  def new_attempts(self, attempts, reference):
    for attempt in attempts:
      start_timestamp = None
      end_timestamp = None
      for record in attempt:
        if record.fields.get('verifier') != TRYJOBVERIFIER:
          continue
        if not start_timestamp:
          if record.fields.get('action') == 'verifier_retry':
            start_timestamp = record.timestamp
        elif record.fields.get('action') in tryjobverifier_terminator_actions:
          end_timestamp = record.timestamp
          duration = (end_timestamp - start_timestamp).total_seconds()
          self.points.append((duration, reference))
          if record.fields.get('action') == 'verifier_retry':
            start_timestamp = end_timestamp
          else:
            start_timestamp = None


class TryjobverifierTotalDurations(ListAnalyzer):  # pragma: no cover
  description = 'Total time spent per CQ attempt on tryjob verifier runs.'
  unit = 'seconds'
  def new_attempts(self, attempts, reference):
    for attempt in attempts:
      start_timestamp = None
      end_timestamp = None
      for record in attempt:
        if record.fields.get('verifier') != TRYJOBVERIFIER:
          continue
        if not start_timestamp:
          start_timestamp = record.timestamp
        end_timestamp = record.timestamp
      if start_timestamp:
        duration = (end_timestamp - start_timestamp).total_seconds()
        self.points.append((duration, reference))


def count_actions(attempts, action):  # pragma: no cover
  count = 0
  for attempt in attempts:
    for record in attempt:
      if (record.fields.get('verifier') == TRYJOBVERIFIER and
          record.fields.get('action') == action):
        count += 1
  return count
