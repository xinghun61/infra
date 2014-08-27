# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.cq_stats import CountStats, ListStats # pylint: disable-msg=E0611
from shared.config import TRYJOBVERIFIER

tryjobverifier_terminator_actions = (
  'verifier_pass',
  'verifier_fail',
  'verifier_retry',
  'verifier_timeout',
)

def analyzers(): # pragma: no cover
  return (
    tryjobverifier_start_count,
    tryjobverifier_retry_count,
    tryjobverifier_pass_count,
    tryjobverifier_fail_count,
    tryjobverifier_skip_count,
    tryjobverifier_error_count,
    tryjobverifier_timeout_count,
    tryjobverifier_first_run_durations,
    tryjobverifier_retry_durations,
    tryjobverifier_total_durations,
  )

@CountStats.constructor('Number of tryjob verifier runs started.')
def tryjobverifier_start_count(patchset_attempts): # pragma: no cover
  return count_actions(patchset_attempts, 'verifier_start')

@CountStats.constructor('Number of tryjob verifier runs retried.')
def tryjobverifier_retry_count(patchset_attempts): # pragma: no cover
  return count_actions(patchset_attempts, 'verifier_retry')

@CountStats.constructor('Number of tryjob verifier runs passed.')
def tryjobverifier_pass_count(patchset_attempts): # pragma: no cover
  return count_actions(patchset_attempts, 'verifier_pass')

@CountStats.constructor('Number of tryjob verifier runs failed.')
def tryjobverifier_fail_count(patchset_attempts): # pragma: no cover
  return count_actions(patchset_attempts, 'verifier_fail')

@CountStats.constructor('Number of tryjob verifier runs skipped.')
def tryjobverifier_skip_count(patchset_attempts): # pragma: no cover
  return count_actions(patchset_attempts, 'verifier_skip')

@CountStats.constructor('Number of tryjob verifier runs errored.')
def tryjobverifier_error_count(patchset_attempts): # pragma: no cover
  return count_actions(patchset_attempts, 'verifier_error')

@CountStats.constructor('Number of tryjob verifier runs that timed out.')
def tryjobverifier_timeout_count(patchset_attempts): # pragma: no cover
  return count_actions(patchset_attempts, 'verifier_timeout')

@ListStats.constructor(
    'Time spent on each tryjob verifier first run',
    unit = 'seconds')
def tryjobverifier_first_run_durations(patchset_attempts): # pragma: no cover
  duration_points = []
  for (issue, patchset), attempts in patchset_attempts.items():
    for i, attempt in enumerate(attempts):
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
        duration_points.append((duration, {
          'issue': issue,
          'patchset': patchset,
          'attempt': i + 1,
        }))
  return duration_points

@ListStats.constructor(
    'Time spent on each tryjob verifier retry.',
    unit = 'seconds')
def tryjobverifier_retry_durations(patchset_attempts): # pragma: no cover
  duration_points = []
  for (issue, patchset), attempts in patchset_attempts.items():
    for i, attempt in enumerate(attempts):
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
          duration_points.append((duration, {
            'issue': issue,
            'patchset': patchset,
            'attempt': i + 1,
          }))
          if record.fields.get('action') == 'verifier_retry':
            start_timestamp = end_timestamp
          else:
            start_timestamp = None
  return duration_points

@ListStats.constructor(
  'Total time spent per CQ attempt on tryjob verifier runs',
  unit = 'seconds')
def tryjobverifier_total_durations(patchset_attempts): # pragma: no cover
  duration_points = []
  for (issue, patchset), attempts in patchset_attempts.items():
    for i, attempt in enumerate(attempts):
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
        duration_points.append((duration, {
          'issue': issue,
          'patchset': patchset,
          'attempt': i + 1,
        }))
  return duration_points

def count_actions(patchset_attempts, action): # pragma: no cover
  count = 0
  for attempts in patchset_attempts.values():
    for attempt in attempts:
      for record in attempt:
        if (record.fields.get('verifier') == TRYJOBVERIFIER and
            record.fields.get('action') == action):
          count += 1
  return count
