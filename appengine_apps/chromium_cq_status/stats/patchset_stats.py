# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple

from shared.config import (
  TRYJOBVERIFIER,
)
from stats.analyzer import (
  AnalyzerGroup,
  CountAnalyzer,
  ListAnalyzer,
)

IssueReference = namedtuple('IssueReference', 'issue')

class PatchsetAnalyzer(AnalyzerGroup):
  def __init__(self):  # pragma: no cover
    super(PatchsetAnalyzer, self).__init__(
      AttemptCount,
      AttemptDurations,
      AttemptFalseRejectCount,
      AttemptFalseRejectCommitCount,
      AttemptFalseRejectCQPresubmitCount,
      AttemptFalseRejectTriggerCount,
      AttemptFalseRejectTryjobCount,
      BlockedOnClosedTreeDurations,
      BlockedOnThrottledTreeDurations,
      IssueCount,
      PatchsetAttempts,
      PatchsetCount,
      PatchsetCommitCount,
      PatchsetCommitDurations,
      PatchsetDurations,
      PatchsetFalseRejectCount,
      PatchsetRejectCount,
      PatchsetTotalCommitQueueDurations,
      PatchsetTotalWallTimeDurations,
    )


class AttemptCount(CountAnalyzer):  # pragma: no cover
  description = 'Number of CQ attempts made.'
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    self.tally[reference] += len(interval_attempts)


class AttemptDurations(ListAnalyzer):  # pragma: no cover
  description = 'Total time spent per CQ attempt.'
  unit = 'seconds'
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    for attempt in interval_attempts:
      delta = attempt[-1].timestamp - attempt[0].timestamp
      self.points.append((delta.total_seconds(), reference))


class AttemptFalseRejectCount(CountAnalyzer):  # pragma: no cover
  description = ('Number of failed attempts on a committed patch that passed '
                 'presubmit, had all LGTMs and were not manually cancelled.')
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    if has_any_actions(all_attempts, ('patch_committed',)):
      self.tally[reference] = sum(1
          for attempt in all_attempts
          for record in attempt
          if is_flaky_failure_record(record))


class AttemptFalseRejectCommitCount(CountAnalyzer):  # pragma: no cover
  description = ('Number of failed commit attempts on a committed patch.')
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    if has_any_actions(all_attempts, ('patch_committed',)):
      self.tally[reference] = sum(1
          for attempt in all_attempts
          for record in attempt
          if is_failure_record('failed_commit', record))


class AttemptFalseRejectCQPresubmitCount(CountAnalyzer):  # pragma: no cover
  description = ('Number of failed CQ presubmit checks on a committed patch.')
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    if has_any_actions(all_attempts, ('patch_committed',)):
      self.tally[reference] = sum(1
          for attempt in all_attempts
          for record in attempt
          if is_failure_record('failed_presubmit_check', record))


class AttemptFalseRejectTriggerCount(CountAnalyzer):  # pragma: no cover
  description = ('Number of failed job trigger attempts on a committed patch.')
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    if has_any_actions(all_attempts, ('patch_committed',)):
      self.tally[reference] = sum(1
          for attempt in all_attempts
          for record in attempt
          if is_failure_record('failed_to_trigger_jobs', record))


class AttemptFalseRejectTryjobCount(CountAnalyzer):  # pragma: no cover
  description = ('Number of failed job attempts on a committed patch.')
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    if has_any_actions(all_attempts, ('patch_committed',)):
      self.tally[reference] = sum(1
          for attempt in all_attempts
          for record in attempt
          if is_failure_record('failed_jobs', record))


class BlockedOnClosedTreeDurations(ListAnalyzer):  # pragma: no cover
  description = 'Time spent per committed patchset blocked on a closed tree.'
  unit = 'seconds'
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    duration = duration_between_actions(
        interval_attempts, 'patch_tree_closed', 'patch_ready_to_commit', False)
    if duration != None:
      self.points.append((duration, reference))


class BlockedOnThrottledTreeDurations(ListAnalyzer):  # pragma: no cover
  description = 'Time spent per committed patchset blocked on a throttled tree.'
  unit = 'seconds'
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    duration = duration_between_actions(
        interval_attempts, 'patch_throttled', 'patch_ready_to_commit', False)
    if duration != None:
      self.points.append((duration, reference))


class IssueCount(CountAnalyzer):  # pragma: no cover
  description = 'Number of issues processed by the CQ.'
  def __init__(self):
    super(IssueCount, self).__init__()
    self.seen_issues = set()

  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    issue = reference.issue
    if issue not in self.seen_issues:
      self.seen_issues.add(issue)
      self.tally[IssueReference(issue)] += 1


class PatchsetAttempts(ListAnalyzer):  # pragma: no cover
  description = 'Number of CQ attempts per patchset.'
  unit = 'attempts'
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    self.points.append((len(interval_attempts), reference))


class PatchsetCount(CountAnalyzer):  # pragma: no cover
  description = 'Number of patchsets processed by the CQ.'
  def __init__(self):
    super(PatchsetCount, self).__init__()
    self.seen_patchsets = set()

  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    if reference not in self.seen_patchsets:
      self.seen_patchsets.add(reference)
      self.tally[reference] += 1


class PatchsetCommitCount(CountAnalyzer):  # pragma: no cover
  description = 'Number of patchsets committed by the CQ.'
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    if has_any_actions(interval_attempts, ('patch_committed',)):
      self.tally[reference] += 1


class PatchsetCommitDurations(ListAnalyzer):  # pragma: no cover
  description = 'Time taken by the CQ to land a patch after passing all checks.'
  unit = 'seconds'
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    duration = duration_between_actions(
        interval_attempts, 'patch_committing', 'patch_committed', True)
    if duration != None:
      self.points.append((duration, reference))

class PatchsetDurations(ListAnalyzer):  # pragma: no cover
  description = ('Total time spent in the CQ per patchset, '
                 'counts multiple CQ attempts as one.')
  unit = 'seconds'
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    duration = 0
    for attempt in interval_attempts:
      delta = attempt[-1].timestamp - attempt[0].timestamp
      duration += delta.total_seconds()
    self.points.append((duration, reference))


class PatchsetFalseRejectCount(CountAnalyzer):  # pragma: no cover
  description = ('Number of patchsets rejected by the trybots '
                 'that eventually passed.')
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    if (has_any_actions(interval_attempts, ('verifier_retry', 'verifier_fail'))
        and has_any_actions(interval_attempts, ('verifier_pass',))):
      self.tally[reference] += 1


class PatchsetRejectCount(CountAnalyzer):  # pragma: no cover
  description = 'Number of patchsets rejected by the trybots at least once.'
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    if has_any_actions(interval_attempts, ('verifier_retry', 'verifier_fail')):
      self.tally[reference] += 1


class PatchsetTotalCommitQueueDurations(ListAnalyzer):  # pragma: no cover
  description = 'Total time spent in the CQ per patch.'
  unit = 'seconds'
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    duration = 0
    for attempt in all_attempts:
      duration += (attempt[-1].timestamp - attempt[0].timestamp).total_seconds()
    self.points.append((duration, reference))


class PatchsetTotalWallTimeDurations(ListAnalyzer):  # pragma: no cover
  description = 'Total time per patch since their commit box was checked.'
  unit = 'seconds'
  def new_attempts(self, project, reference, all_attempts, interval_attempts):
    assert len(all_attempts) > 0
    first_start = all_attempts[0][0]
    latest_stop = all_attempts[-1][-1]
    duration = (latest_stop.timestamp - first_start.timestamp).total_seconds()
    self.points.append((duration, reference))


def has_any_actions(attempts, actions):  # pragma: no cover
  assert type(actions) in (tuple, list)
  for attempt in attempts:
    for record in attempt:
      action = record.fields.get('action')
      if action in actions:
        if (action.startswith('verifier_') and
            record.fields.get('verifier') != TRYJOBVERIFIER):
          continue
        return True
  return False


def duration_between_actions(attempts, action_start, action_end,
    requires_start):  # pragma: no cover
  '''Counts the duration between start and end actions per patchset

  The end action must be present for the duration to be recorded.
  It is optional whether the start action needs to be present.
  An absent start action counts as a 0 duration.'''
  duration_valid = False
  duration = 0
  for attempt in attempts:
    start_timestamp = None
    for record in attempt:
      if not start_timestamp and record.fields.get('action') == action_start:
        start_timestamp = record.timestamp
      if ((start_timestamp or not requires_start) and
          record.fields.get('action') == action_end):
        duration_valid = True
        if start_timestamp:
          duration += (record.timestamp - start_timestamp).total_seconds()
          start_timestamp = None
  if duration_valid:
    return duration
  return None


def is_flaky_failure_record(record):  # pragma: no cover
  if record.fields.get('action') == 'patch_failed':
    fail_type = record.fields.get('reason', {}).get('fail_type')
    valid_fail = fail_type in (
      'failed_presubmit_bot',
      'missing_lgtm',
      'not_lgtm',
    )
    if valid_fail:
      return False
    message = record.fields.get('message')
    valid_fail = message and (
      'No LGTM' in message or
      'A disapproval has been posted' in message or
      'Failed to apply' in message or
      'Presubmit check' in message or
      'Transient error: Invalid delimiter' in message or
      ('Try jobs failed' in message and 'presubmit' in message))
    return not valid_fail
  return False


def is_failure_record(fail_type_check, record):  # pragma: no cover
  action = record.fields.get('action')
  fail_type = record.fields.get('reason', {}).get('fail_type')
  return action == 'patch_failed' and fail_type == fail_type_check
