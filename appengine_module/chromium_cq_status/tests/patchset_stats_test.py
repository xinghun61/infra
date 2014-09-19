# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# StatsTest must be imported first in order to get proper ndb monkeypatching.
from appengine_module.chromium_cq_status.tests.stats_test import StatsTest, hours  # pylint: disable=C0301
from appengine_module.chromium_cq_status.stats.analysis import PatchsetReference
from appengine_module.chromium_cq_status.stats.patchset_stats import IssueReference  # pylint: disable=C0301

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
          (hours(10), PatchsetReference(1, 1)),
          (hours(12), PatchsetReference(2, 1)),
        ),
      ), self.get_stats('attempt-durations'))

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
