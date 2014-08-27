# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model.cq_stats import CountStats, ListStats # pylint: disable-msg=E0611
from shared.config import TRYJOBVERIFIER

def analyzers():
  return (
    issue_count,
    patchset_count,
    patchset_commit_count,
    patchset_reject_count,
    patchset_false_reject_count,
    patchset_durations,
    attempt_count,
    attempt_durations,
    blocked_on_closed_tree_durations,
    blocked_on_throttled_tree_durations,
    commit_durations,
  )

@CountStats.constructor('Number of issues processed by the CQ.')
def issue_count(patchset_attempts): # pragma: no cover
  return len(set(issue for issue, _ in patchset_attempts))

@CountStats.constructor('Number of patchsets processed by the CQ.')
def patchset_count(patchset_attempts): # pragma: no cover
  return len(patchset_attempts)

@CountStats.constructor('Number of patchsets committed by the CQ.')
def patchset_commit_count(patchset_attempts): # pragma: no cover
  return count_patchsets_with_actions(patchset_attempts, ('patch_committed',))

@CountStats.constructor(
    'Number of patchsets rejected by the trybots at least once.')
def patchset_reject_count(patchset_attempts): # pragma: no cover
  return count_patchsets_with_actions(patchset_attempts,
      ('verifier_retry', 'verifier_fail'))

@CountStats.constructor(
    'Number of patchsets rejected by the trybots that eventually landed.')
def patchset_false_reject_count(patchset_attempts): # pragma: no cover
  count = 0
  for attempts in patchset_attempts.values():
    if (has_any_actions(attempts, ('verifier_retry',)) and
        has_any_actions(attempts, ('patch_committing',))):
      count += 1
  return count

@ListStats.constructor(
    'Total time spent in the CQ per patchset, '
    'counts multiple CQ attempts as one.',
    unit = 'seconds')
def patchset_durations(patchset_attempts): # pragma: no cover
  duration_points = []
  for (issue, patchset), attempts in patchset_attempts.items():
    duration = 0
    for attempt in attempts:
      delta = attempt[-1].timestamp - attempt[0].timestamp
      duration += delta.total_seconds()
    duration_points.append((duration, {
      'issue': issue,
      'patchset': patchset,
    }))
  return duration_points

@CountStats.constructor('Number of CQ attempts made.')
def attempt_count(patchset_attempts): # pragma: no cover
  return sum(map(len, patchset_attempts))

@ListStats.constructor(
    'Total time spent per CQ attempt.',
    unit = 'seconds')
def attempt_durations(patchset_attempts): # pragma: no cover
  duration_points = []
  for (issue, patchset), attempts in patchset_attempts.items():
    for i, attempt in enumerate(attempts):
      delta = attempt[-1].timestamp - attempt[0].timestamp
      duration_points.append((delta.total_seconds(), {
        'issue': issue,
        'patchset': patchset,
        'attempt': i + 1,
      }))
  return duration_points

@ListStats.constructor(
    'Time spent per committed patchset blocked on a closed tree.',
    unit = 'seconds')
def blocked_on_closed_tree_durations(patchset_attempts): # pragma: no cover
  return duration_between_actions_points(patchset_attempts,
      'patch_tree_closed', 'patch_committing', False)

@ListStats.constructor(
    'Time spent per committed patchset blocked on a throttled tree.',
    unit = 'seconds')
def blocked_on_throttled_tree_durations(patchset_attempts): # pragma: no cover
  return duration_between_actions_points(patchset_attempts,
      'patch_throttled', 'patch_committing', False)

@ListStats.constructor(
    'Time taken by the CQ to land a patch after passing all checks.',
    unit = 'seconds')
def commit_durations(patchset_attempts): # pragma: no cover
  return duration_between_actions_points(patchset_attempts,
      'patch_committing', 'patch_committed', True)

def count_patchsets_with_actions(patchset_attempts, actions): # pragma: no cover
  count = 0
  for attempts in patchset_attempts.values():
    if has_any_actions(attempts, actions):
      count += 1
  return count

def has_any_actions(attempts, actions): # pragma: no cover
  for attempt in attempts:
    for record in attempt:
      action = record.fields.get('action')
      if action in actions:
        if (action.startswith('verifier_') and
            record.fields.get('verifier') != TRYJOBVERIFIER):
          continue
        return True
  return False

def duration_between_actions_points(patchset_attempts,
    action_start, action_end, requires_start): # pragma: no cover
  '''Counts the duration between start and end actions per patchset

  The end action must be present for the duration to be recorded.
  It is optional whether the start action needs to be present.
  An absent start action counts as a 0 duration.'''
  duration_points = []
  for (issue, patchset), attempts in patchset_attempts.items():
    start_found = False
    end_found = False
    duration = 0
    for attempt in attempts:
      start_timestamp = None
      for record in attempt:
        if not start_timestamp and record.fields.get('action') == action_start:
          start_found = True
          start_timestamp = record.timestamp
        if start_timestamp and record.fields.get('action') == action_end:
          end_found = True
          duration += (record.timestamp - start_timestamp).total_seconds()
          start_timestamp = None
    if (start_found or not requires_start) and end_found:
      duration_points.append((duration, {
        'issue': issue,
        'patchset': patchset,
      }))
  return duration_points
