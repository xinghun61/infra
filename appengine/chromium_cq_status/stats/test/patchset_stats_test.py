# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import itertools

# StatsTest must be imported first in order to get proper ndb monkeypatching.
from stats.analysis import PatchsetReference
from stats.patchset_stats import IssueReference
from stats.test.stats_test import StatsTest, hours

class PatchsetStatsTest(StatsTest):
  attempt_records = (
    (-3, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
    (-2, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
    (-1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
    (1, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
    (5, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
    (9, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
    (10, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
    (17, {'issue': 2, 'patchset': 1,'action': 'patch_stop'}),
    (20, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
  )

  def test_attempt_count(self):
    self.analyze_records(*self.attempt_records)
    self.assertEquals(self.create_count(
        name='attempt-count',
        description='Number of CQ attempts made.',
        tally={
          PatchsetReference(1, 1): 2,
          PatchsetReference(2, 1): 1,
        },
      ), self.get_stats('attempt-count'))

  def test_attempt_durations(self):
    self.analyze_records(*self.attempt_records)
    self.assertEquals(self.create_list(
        name='attempt-durations',
        description='Total time spent per CQ attempt.',
        unit='seconds',
        points=(
          (hours(2), PatchsetReference(1, 1)),
          (hours(11), PatchsetReference(1, 1)),
          (hours(12), PatchsetReference(2, 1)),
        ),
      ), self.get_stats('attempt-durations'))

  def false_reject_message_records(issue, message): # pylint: disable=E0213
    return (
      (0, {'issue': issue, 'patchset': 1, 'action': 'patch_start'}),
      (1, {'issue': issue, 'patchset': 1, 'action': 'patch_failed',
          'message': message}),
      (2, {'issue': issue, 'patchset': 1, 'action': 'patch_stop'}),
      (3, {'issue': issue, 'patchset': 1, 'action': 'patch_start'}),
      (4, {'issue': issue, 'patchset': 1, 'action': 'patch_committed'}),
      (5, {'issue': issue, 'patchset': 1, 'action': 'patch_stop'}),
    )

  def false_reject_fail_type_records(issue, fail_type): # pylint: disable=E0213,C0301
    return (
      (0, {'issue': issue, 'patchset': 1, 'action': 'patch_start'}),
      (1, {'issue': issue, 'patchset': 1, 'action': 'patch_failed',
          'reason': {'fail_type': fail_type}}),
      (2, {'issue': issue, 'patchset': 1, 'action': 'patch_stop'}),
      (3, {'issue': issue, 'patchset': 1, 'action': 'patch_start'}),
      (4, {'issue': issue, 'patchset': 1, 'action': 'patch_committed'}),
      (5, {'issue': issue, 'patchset': 1, 'action': 'patch_stop'}),
    )

  false_reject_attempt_records = itertools.chain((
      (0, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
      (1, {'issue': 1, 'patchset': 1, 'action': 'patch_failed'}),
      (2, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
      (3, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
      (4, {'issue': 1, 'patchset': 1, 'action': 'patch_committed'}),
      (5, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),

      (0, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
      (1, {'issue': 2, 'patchset': 1, 'action': 'patch_failed'}),
      (2, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
      (3, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
      (4, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),

      (0, {'issue': 3, 'patchset': 1, 'action': 'patch_start'}),
      (1, {'issue': 3, 'patchset': 1, 'action': 'patch_stop',
          'message': 'CQ bit was unchecked on CL'}),
      (2, {'issue': 3, 'patchset': 1, 'action': 'patch_start'}),
      (3, {'issue': 3, 'patchset': 1, 'action': 'patch_committed'}),
      (4, {'issue': 3, 'patchset': 1, 'action': 'patch_stop'}),

      (0, {'issue': 4, 'patchset': 1, 'action': 'patch_start'}),
      (1, {'issue': 4, 'patchset': 1, 'action': 'patch_stop',
          'message': 'A disapproval has been posted'}),
      (2, {'issue': 4, 'patchset': 1, 'action': 'patch_start'}),
      (3, {'issue': 4, 'patchset': 1, 'action': 'patch_committed'}),
      (4, {'issue': 4, 'patchset': 1, 'action': 'patch_stop'}),

      (-6, {'issue': 5, 'patchset': 1, 'action': 'patch_start'}),
      (-5, {'issue': 5, 'patchset': 1, 'action': 'patch_failed'}),
      (-4, {'issue': 5, 'patchset': 1, 'action': 'patch_stop'}),
      (-3, {'issue': 5, 'patchset': 1, 'action': 'patch_start'}),
      (-2, {'issue': 5, 'patchset': 1, 'action': 'patch_failed'}),
      (-1, {'issue': 5, 'patchset': 1, 'action': 'patch_stop'}),
      (0, {'issue': 5, 'patchset': 1, 'action': 'patch_start'}),
      (1, {'issue': 5, 'patchset': 1, 'action': 'patch_committed'}),
      (2, {'issue': 5, 'patchset': 1, 'action': 'patch_stop'}),

      (20, {'issue': 6, 'patchset': 1, 'action': 'patch_start'}),
      (21, {'issue': 6, 'patchset': 1, 'action': 'patch_stop'}),
      (22, {'issue': 6, 'patchset': 1, 'action': 'patch_start'}),
      (23, {'issue': 6, 'patchset': 1, 'action': 'patch_committed'}),
      (24, {'issue': 6, 'patchset': 1, 'action': 'patch_stop'}),

      (0, {'issue': 7, 'patchset': 1, 'action': 'patch_start'}),
      (1, {'issue': 7, 'patchset': 1, 'action': 'patch_failed',
          'reason': None}),
      (2, {'issue': 7, 'patchset': 1, 'action': 'patch_stop'}),
      (3, {'issue': 7, 'patchset': 1, 'action': 'patch_start'}),
      (4, {'issue': 7, 'patchset': 1, 'action': 'patch_committed'}),
      (5, {'issue': 7, 'patchset': 1, 'action': 'patch_stop'}),
    ),
    false_reject_message_records(8, 'Presubmit check'),
    false_reject_message_records(9, 'Transient error: Invalid delimiter'),
    false_reject_message_records(10, 'Try jobs failed: project_tester'),
    false_reject_message_records(11, 'Try jobs failed: project_presubmit'),
    false_reject_message_records(12, 'No LGTM'),
    false_reject_message_records(13, 'Failed to apply'),
    false_reject_message_records(14, ''),
    false_reject_fail_type_records(15, 'failed_commit'),
    false_reject_fail_type_records(16, 'failed_presubmit_check'),
    false_reject_fail_type_records(17, 'failed_presubmit_bot'),
    false_reject_fail_type_records(18, 'failed_jobs'),
    false_reject_fail_type_records(19, 'failed_to_trigger_jobs'),
    false_reject_fail_type_records(20, 'missing_lgtm'),
    false_reject_fail_type_records(21, 'not_lgtm'),
    false_reject_fail_type_records(22, ''), (
    )
  )

  def test_attempt_false_reject_count(self):
    self.analyze_records(*self.false_reject_attempt_records)
    self.assertEquals(self.create_count(
        name='attempt-false-reject-count',
        description=('Number of failed attempts on a committed '
                     'patch that passed presubmit, had all LGTMs '
                     'and were not manually cancelled.'),
        tally={
          PatchsetReference(1, 1): 1,
          PatchsetReference(5, 1): 2,
          PatchsetReference(7, 1): 1,
          PatchsetReference(10, 1): 1,
          PatchsetReference(14, 1): 1,
          PatchsetReference(15, 1): 1,
          PatchsetReference(16, 1): 1,
          PatchsetReference(18, 1): 1,
          PatchsetReference(19, 1): 1,
          PatchsetReference(22, 1): 1,
        },
      ), self.get_stats('attempt-false-reject-count'))

    self.assertEquals(self.create_count(
        name='attempt-false-reject-commit-count',
        description='Number of failed commit attempts on a committed patch.',
        tally={PatchsetReference(15, 1): 1},
      ), self.get_stats('attempt-false-reject-commit-count'))

    self.assertEquals(self.create_count(
        name='attempt-false-reject-cq-presubmit-count',
        description=('Number of failed CQ presubmit checks on a committed '
                     'patch.'),
        tally={PatchsetReference(16, 1): 1},
      ), self.get_stats('attempt-false-reject-cq-presubmit-count'))

    self.assertEquals(self.create_count(
        name='attempt-false-reject-trigger-count',
        description=('Number of failed job trigger attempts on a committed '
                     'patch.'),
        tally={PatchsetReference(19, 1): 1},
      ), self.get_stats('attempt-false-reject-trigger-count'))

    self.assertEquals(self.create_count(
        name='attempt-false-reject-tryjob-count',
        description='Number of failed job attempts on a committed patch.',
        tally={PatchsetReference(18, 1): 1},
      ), self.get_stats('attempt-false-reject-tryjob-count'))

  def test_blocked_on_closed_tree_durations(self):
    self.analyze_records(
      (1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
      (2, {'issue': 1, 'patchset': 1, 'action': 'patch_tree_closed'}),
      (3, {'issue': 1, 'patchset': 1, 'action': 'patch_ready_to_commit'}),
      (4, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
      (5, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
      (6, {'issue': 2, 'patchset': 1, 'action': 'patch_tree_closed'}),
      (9, {'issue': 2, 'patchset': 1, 'action': 'patch_ready_to_commit'}),
      (10, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
      (11, {'issue': 3, 'patchset': 2, 'action': 'patch_start'}),
      (12, {'issue': 3, 'patchset': 2, 'action': 'patch_tree_closed'}),
      (14, {'issue': 3, 'patchset': 2, 'action': 'patch_stop'}),
      (15, {'issue': 4, 'patchset': 2, 'action': 'patch_start'}),
      (19, {'issue': 4, 'patchset': 2, 'action': 'patch_ready_to_commit'}),
      (20, {'issue': 4, 'patchset': 2, 'action': 'patch_stop'}),
    )
    self.assertEquals(self.create_list(
        name='blocked-on-closed-tree-durations',
        description=('Time spent per committed patchset '
                     'blocked on a closed tree.'),
        unit='seconds',
        points=(
          (hours(1), PatchsetReference(1, 1)),
          (hours(3), PatchsetReference(2, 1)),
          (hours(0), PatchsetReference(4, 2)),
        ),
      ), self.get_stats('blocked-on-closed-tree-durations'))

  def test_blocked_on_throttled_tree_durations(self):
    self.analyze_records(
      (1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
      (2, {'issue': 1, 'patchset': 1, 'action': 'patch_throttled'}),
      (3, {'issue': 1, 'patchset': 1, 'action': 'patch_ready_to_commit'}),
      (4, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
      (5, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
      (6, {'issue': 2, 'patchset': 1, 'action': 'patch_throttled'}),
      (9, {'issue': 2, 'patchset': 1, 'action': 'patch_ready_to_commit'}),
      (10, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
      (11, {'issue': 3, 'patchset': 2, 'action': 'patch_start'}),
      (12, {'issue': 3, 'patchset': 2, 'action': 'patch_throttled'}),
      (14, {'issue': 3, 'patchset': 2, 'action': 'patch_stop'}),
      (15, {'issue': 4, 'patchset': 2, 'action': 'patch_start'}),
      (19, {'issue': 4, 'patchset': 2, 'action': 'patch_ready_to_commit'}),
      (20, {'issue': 4, 'patchset': 2, 'action': 'patch_stop'}),
    )
    self.assertEquals(self.create_list(
        name='blocked-on-throttled-tree-durations',
        description=('Time spent per committed patchset '
                     'blocked on a throttled tree.'),
        unit='seconds',
        points=(
          (hours(1), PatchsetReference(1, 1)),
          (hours(3), PatchsetReference(2, 1)),
          (hours(0), PatchsetReference(4, 2)),
        ),
      ), self.get_stats('blocked-on-throttled-tree-durations'))

  issue_patchset_count_records = (
    (1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
    (2, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
    (3, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
    (4, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
    (5, {'issue': 3, 'patchset': 1, 'action': 'patch_start'}),
    (6, {'issue': 3, 'patchset': 1, 'action': 'patch_stop'}),
    (7, {'issue': 3, 'patchset': 2, 'action': 'patch_start'}),
    (8, {'issue': 3, 'patchset': 2, 'action': 'patch_stop'}),
    (9, {'issue': 3, 'patchset': 2, 'action': 'patch_start'}),
    (10, {'issue': 3, 'patchset': 2, 'action': 'patch_stop'}),
  )

  def test_issue_count(self):
    self.analyze_records(*self.issue_patchset_count_records)
    self.assertEquals(self.create_count(
        name='issue-count',
        description='Number of issues processed by the CQ.',
        tally={
          IssueReference(1): 1,
          IssueReference(2): 1,
          IssueReference(3): 1,
        },
      ), self.get_stats('issue-count'))

  def test_patchset_attempts(self):
    self.analyze_records(*self.issue_patchset_count_records)
    self.assertEquals(self.create_list(
        name='patchset-attempts',
        description='Number of CQ attempts per patchset.',
        unit='attempts',
        points=(
          (1, PatchsetReference(1, 1)),
          (1, PatchsetReference(2, 1)),
          (1, PatchsetReference(3, 1)),
          (2, PatchsetReference(3, 2)),
        ),
      ), self.get_stats('patchset-attempts'))

  def test_patchset_count(self):
    self.analyze_records(*self.issue_patchset_count_records)
    self.assertEquals(self.create_count(
        name='patchset-count',
        description='Number of patchsets processed by the CQ.',
        tally={
          PatchsetReference(1, 1): 1,
          PatchsetReference(2, 1): 1,
          PatchsetReference(3, 1): 1,
          PatchsetReference(3, 2): 1,
        },
      ), self.get_stats('patchset-count'))

  patchset_commit_records = (
    (1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
    (2, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
    (3, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
    (4, {'issue': 2, 'patchset': 1, 'action': 'patch_committing'}),
    (5, {'issue': 2, 'patchset': 1, 'action': 'patch_committed'}),
    (6, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
    (7, {'issue': 3, 'patchset': 1, 'action': 'patch_start'}),
    (8, {'issue': 3, 'patchset': 1, 'action': 'patch_stop'}),
    (10, {'issue': 3, 'patchset': 2, 'action': 'patch_start'}),
    (11, {'issue': 3, 'patchset': 2, 'action': 'patch_committing'}),
    (15, {'issue': 3, 'patchset': 2, 'action': 'patch_committed'}),
    (16, {'issue': 3, 'patchset': 2, 'action': 'patch_stop'}),
    (18, {'issue': 4, 'patchset': 1, 'action': 'patch_start'}),
    (19, {'issue': 4, 'patchset': 1, 'action': 'patch_committing'}),
    (20, {'issue': 4, 'patchset': 1, 'action': 'patch_stop'}),
  )

  def test_patchset_commit_count(self):
    self.analyze_records(*self.patchset_commit_records)
    self.assertEquals(self.create_count(
        name='patchset-commit-count',
        description='Number of patchsets committed by the CQ.',
        tally={
          PatchsetReference(2, 1): 1,
          PatchsetReference(3, 2): 1,
        },
      ), self.get_stats('patchset-commit-count'))

  def test_patchset_commit_durations(self):
    self.analyze_records(*self.patchset_commit_records)
    self.assertEquals(self.create_list(
        name='patchset-commit-durations',
        description=('Time taken by the CQ to land a patch '
                     'after passing all checks.'),
        unit='seconds',
        points=(
          (hours(1), PatchsetReference(2, 1)),
          (hours(4), PatchsetReference(3, 2)),
        ),
      ), self.get_stats('patchset-commit-durations'))

  def test_patchset_durations(self):
    self.analyze_records(
      (1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
      (2, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
      (3, {'issue': 1, 'patchset': 2, 'action': 'patch_start'}),
      (5, {'issue': 1, 'patchset': 2, 'action': 'patch_stop'}),
      (6, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
      (7, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
      (8, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
      (10, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
      (10, {'issue': 2, 'patchset': 2, 'action': 'patch_start'}),
      (20, {'issue': 2, 'patchset': 2, 'action': 'patch_stop'}),
    )
    self.assertEquals(self.create_list(
        name='patchset-durations',
        description=('Total time spent in the CQ per patchset, '
                     'counts multiple CQ attempts as one.'),
        unit='seconds',
        points=(
          (hours(1), PatchsetReference(1, 1)),
          (hours(2), PatchsetReference(1, 2)),
          (hours(3), PatchsetReference(2, 1)),
          (hours(10), PatchsetReference(2, 2)),
        ),
      ), self.get_stats('patchset-durations'))

  rejected_patchset_records = (
    (1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
    (2, {'issue': 1, 'patchset': 1, 'action': 'verifier_fail'}),
    (3, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
    (4, {'issue': 1, 'patchset': 2, 'action': 'patch_start'}),
    (5, {'issue': 1, 'patchset': 2, 'action': 'verifier_retry'}),
    (6, {'issue': 1, 'patchset': 2, 'action': 'verifier_fail'}),
    (7, {'issue': 1, 'patchset': 2, 'action': 'patch_stop'}),
    (8, {'issue': 1, 'patchset': 2, 'action': 'patch_start'}),
    (9, {'issue': 1, 'patchset': 2, 'action': 'verifier_pass'}),
    (10, {'issue': 1, 'patchset': 2, 'action': 'patch_stop'}),
    (11, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
    (12, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
    (13, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
    (14, {'issue': 2, 'patchset': 1, 'action': 'verifier_pass'}),
    (15, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
    (16, {'issue': 2, 'patchset': 2, 'action': 'patch_start'}),
    (17, {'issue': 2, 'patchset': 2, 'action': 'verifier_retry'}),
    (18, {'issue': 2, 'patchset': 2, 'action': 'verifier_pass'}),
    (19, {'issue': 2, 'patchset': 2, 'action': 'patch_stop'}),
  )

  def test_patchset_false_reject_count(self):
    self.analyze_records(*self.rejected_patchset_records)
    self.assertEquals(self.create_count(
        name='patchset-false-reject-count',
        description=('Number of patchsets rejected by the trybots '
                     'that eventually passed.'),
        tally={
          PatchsetReference(1, 2): 1,
          PatchsetReference(2, 2): 1,
        },
      ), self.get_stats('patchset-false-reject-count'))

  def test_patchset_reject_count(self):
    self.analyze_records(*self.rejected_patchset_records)
    self.assertEquals(self.create_count(
        name='patchset-reject-count',
        description=('Number of patchsets rejected by the trybots '
                     'at least once.'),
        tally={
          PatchsetReference(1, 1): 1,
          PatchsetReference(1, 2): 1,
          PatchsetReference(2, 2): 1,
        },
      ), self.get_stats('patchset-reject-count'))

  historical_records = (
    (-50, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
    (-45, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
    (-30, {'issue': 1, 'patchset': 2, 'action': 'patch_start'}),
    (-25, {'issue': 1, 'patchset': 2, 'action': 'patch_stop'}),
    (-10, {'issue': 1, 'patchset': 2, 'action': 'patch_start'}),
    (-5, {'issue': 1, 'patchset': 2, 'action': 'patch_stop'}),
    (5, {'issue': 1, 'patchset': 2, 'action': 'patch_start'}),
    (6, {'issue': 1, 'patchset': 2, 'action': 'patch_stop'}),
    (10, {'issue': 1, 'patchset': 3, 'action': 'patch_start'}),
    (15, {'issue': 1, 'patchset': 3, 'action': 'patch_stop'}),
    (25, {'issue': 1, 'patchset': 3, 'action': 'patch_start'}),
    (30, {'issue': 1, 'patchset': 3, 'action': 'patch_stop'}),
  )

  def test_patchset_total_commit_queue_durations(self):
    self.analyze_records(*self.historical_records)
    self.assertEquals(self.create_list(
      name='patchset-total-commit-queue-durations',
      description='Total time spent in the CQ per patch.',
      unit='seconds',
      points=(
        (hours(11), PatchsetReference(1, 2)),
        (hours(5), PatchsetReference(1, 3)),
      ),
    ), self.get_stats('patchset-total-commit-queue-durations'))

  def test_patchset_total_wall_time_durations(self):
    self.analyze_records(*self.historical_records)
    self.assertEquals(self.create_list(
      name='patchset-total-wall-time-durations',
      description='Total time per patch since their commit box was checked.',
      unit='seconds',
      points=(
        (hours(36), PatchsetReference(1, 2)),
        (hours(5), PatchsetReference(1, 3)),
      ),
    ), self.get_stats('patchset-total-wall-time-durations'))
