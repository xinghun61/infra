# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple

from google.appengine.ext import ndb

from appengine_module.chromium_cq_status.model.record import Record
from appengine_module.chromium_cq_status.shared.config import (
  TAG_START,
  TAG_STOP,
  TAG_PROJECT,
  TAG_ISSUE,
  TAG_PATCHSET,
  TRYJOBVERIFIER,
)
from appengine_module.chromium_cq_status.stats.analyzer import (
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
  def new_attempts(self, attempts, reference, project):
    self.tally[reference] += len(attempts)


class AttemptDurations(ListAnalyzer):  # pragma: no cover
  description = 'Total time spent per CQ attempt.'
  unit = 'seconds'
  def new_attempts(self, attempts, reference, project):
    for attempt in attempts:
      delta = attempt[-1].timestamp - attempt[0].timestamp
      self.points.append((delta.total_seconds(), reference))


class BlockedOnClosedTreeDurations(ListAnalyzer):  # pragma: no cover
  description = 'Time spent per committed patchset blocked on a closed tree.'
  unit = 'seconds'
  def new_attempts(self, attempts, reference, project):
    duration = duration_between_actions(
        attempts, 'patch_tree_closed', 'patch_ready_to_commit', False)
    if duration != None:
      self.points.append((duration, reference))


class BlockedOnThrottledTreeDurations(ListAnalyzer):  # pragma: no cover
  description = 'Time spent per committed patchset blocked on a throttled tree.'
  unit = 'seconds'
  def new_attempts(self, attempts, reference, project):
    duration = duration_between_actions(
        attempts, 'patch_throttled', 'patch_ready_to_commit', False)
    if duration != None:
      self.points.append((duration, reference))


class IssueCount(CountAnalyzer):  # pragma: no cover
  description = 'Number of issues processed by the CQ.'
  def __init__(self):
    super(IssueCount, self).__init__()
    self.seen_issues = set()

  def new_attempts(self, attempts, reference, project):
    issue = reference.issue
    if issue not in self.seen_issues:
      self.seen_issues.add(issue)
      self.tally[IssueReference(issue)] += 1


class PatchsetAttempts(ListAnalyzer):  # pragma: no cover
  description = 'Number of CQ attempts per patchset.'
  unit = 'attempts'
  def new_attempts(self, attempts, reference, project):
    self.points.append((len(attempts), reference))


class PatchsetCount(CountAnalyzer):  # pragma: no cover
  description = 'Number of patchsets processed by the CQ.'
  def __init__(self):
    super(PatchsetCount, self).__init__()
    self.seen_patchsets = set()

  def new_attempts(self, attempts, reference, project):
    if reference not in self.seen_patchsets:
      self.seen_patchsets.add(reference)
      self.tally[reference] += 1


class PatchsetCommitCount(CountAnalyzer):  # pragma: no cover
  description = 'Number of patchsets committed by the CQ.'
  def new_attempts(self, attempts, reference, project):
    if has_any_actions(attempts, ('patch_committed',)):
      self.tally[reference] += 1


class PatchsetCommitDurations(ListAnalyzer):  # pragma: no cover
  description = 'Time taken by the CQ to land a patch after passing all checks.'
  unit = 'seconds'
  def new_attempts(self, attempts, reference, project):
    duration = duration_between_actions(
        attempts, 'patch_committing', 'patch_committed', True)
    if duration != None:
      self.points.append((duration, reference))

class PatchsetDurations(ListAnalyzer):  # pragma: no cover
  description = ('Total time spent in the CQ per patchset, '
                 'counts multiple CQ attempts as one.')
  unit = 'seconds'
  def new_attempts(self, attempts, reference, project):
    duration = 0
    for attempt in attempts:
      delta = attempt[-1].timestamp - attempt[0].timestamp
      duration += delta.total_seconds()
    self.points.append((duration, reference))


class PatchsetFalseRejectCount(CountAnalyzer):  # pragma: no cover
  description = ('Number of patchsets rejected by the trybots '
                 'that eventually passed.')
  def new_attempts(self, attempts, reference, project):
    if (has_any_actions(attempts, ('verifier_retry', 'verifier_fail')) and
        has_any_actions(attempts, ('verifier_pass',))):
      self.tally[reference] += 1


class PatchsetRejectCount(CountAnalyzer):  # pragma: no cover
  description = 'Number of patchsets rejected by the trybots at least once.'
  def new_attempts(self, attempts, reference, project):
    if has_any_actions(attempts, ('verifier_retry', 'verifier_fail')):
      self.tally[reference] += 1


class PatchsetTotalCommitQueueDurations(ListAnalyzer):  # pragma: no cover
  description = 'Total time spent in the CQ per patch.'
  unit = 'seconds'
  def new_attempts(self, attempts, reference, project):
    duration = 0
    for attempt in attempts:
      duration += (attempt[-1].timestamp - attempt[0].timestamp).total_seconds()

    assert len(attempts) > 0
    query = Record.query().order(Record.timestamp).filter(
      Record.timestamp < attempts[0][0].timestamp,
      Record.tags == TAG_PROJECT % project,
      Record.tags == TAG_ISSUE % reference.issue,
      Record.tags == TAG_PATCHSET % reference.patchset,
      ndb.OR(Record.tags == TAG_START, Record.tags == TAG_STOP))
    last_start = None
    for record in query:
      if last_start == None:
        if TAG_START in record.tags:
          last_start = record.timestamp
      else:
        if TAG_STOP in record.tags:
          duration += (record.timestamp - last_start).total_seconds()
          last_start = None

    self.points.append((duration, reference))


class PatchsetTotalWallTimeDurations(ListAnalyzer):  # pragma: no cover
  description = 'Total time per patch since their commit box was checked.'
  unit = 'seconds'
  def new_attempts(self, attempts, reference, project):
    assert len(attempts) > 0
    latest_stop = attempts[-1][-1]
    first_start = Record.query().order(Record.timestamp).filter(
      Record.tags == TAG_PROJECT % project,
      Record.tags == TAG_ISSUE % reference.issue,
      Record.tags == TAG_PATCHSET % reference.patchset,
      Record.tags == TAG_START).get()
    if first_start:
      duration = (latest_stop.timestamp - first_start.timestamp).total_seconds()
      self.points.append((duration, reference))


def has_any_actions(attempts, actions):  # pragma: no cover
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
  start_found = False
  duration_valid = False
  duration = 0
  for attempt in attempts:
    start_timestamp = None
    for record in attempt:
      if not start_timestamp and record.fields.get('action') == action_start:
        start_found = True
        start_timestamp = record.timestamp
      if ((start_found or not requires_start) and
          record.fields.get('action') == action_end):
        duration_valid = True
        if start_found:
          duration += (record.timestamp - start_timestamp).total_seconds()
          start_found = False
          start_timestamp = None
  if duration_valid:
    return duration
  return None
