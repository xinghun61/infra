# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from shared.config import TRYJOBVERIFIER
from stats.analyzer import (
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

class TryjobverifierAnalyzer(AnalyzerGroup):
  def __init__(self):
    super(TryjobverifierAnalyzer, self).__init__(
      TryjobverifierActionCountGroup,
      TryjobverifierFirstRunDurations,
      TryjobverifierRetryDurations,
      TryjobverifierTotalDurations,
    )

class TryjobverifierActionCount(CountAnalyzer):
  def __init__(self, action, description):
    super(TryjobverifierActionCount, self).__init__()
    self.action = action
    self.description = description

  def new_patchset_attempts(self, issue, patchset, attempts):
    self.count += count_actions(attempts, 'verifier_' + self.action)

  def _get_name(self):
    return 'tryjobverifier_%s_count' % self.action

class TryjobverifierActionCountGroup(AnalyzerGroup):
  def __init__(self):
    self.analyzers = []
    for action, description in counted_actions:
      self.analyzers.append(TryjobverifierActionCount(action, description))

class TryjobverifierFirstRunDurations(ListAnalyzer):
  description = 'Time spent on each tryjob verifier first run.'
  unit = 'seconds'
  def new_patchset_attempts(self, issue, patchset, attempts):
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
        self.points.append((duration, {
          'issue': issue,
          'patchset': patchset,
        }))

class TryjobverifierRetryDurations(ListAnalyzer):
  description = 'Time spent on each tryjob verifier retry.'
  unit = 'seconds'
  def new_patchset_attempts(self, issue, patchset, attempts):
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
          self.points.append((duration, {
            'issue': issue,
            'patchset': patchset,
          }))
          if record.fields.get('action') == 'verifier_retry':
            start_timestamp = end_timestamp
          else:
            start_timestamp = None

class TryjobverifierTotalDurations(ListAnalyzer):
  description = 'Total time spent per CQ attempt on tryjob verifier runs.'
  unit = 'seconds'
  def new_patchset_attempts(self, issue, patchset, attempts):
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
        self.points.append((duration, {
          'issue': issue,
          'patchset': patchset,
        }))

def count_actions(attempts, action):
  count = 0
  for attempt in attempts:
    for record in attempt:
      if (record.fields.get('verifier') == TRYJOBVERIFIER and
          record.fields.get('action') == action):
        count += 1
  return count
