# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# StatsTest must be imported first in order to get proper ndb monkeypatching.
from appengine_module.chromium_cq_status.tests.stats_test import StatsTest, hours  # pylint: disable=C0301
from appengine_module.chromium_cq_status.stats.analysis import PatchsetReference


class TryjobverifierStatsTest(StatsTest):
  def test_tryjobverifier_simple_count(self):
    counted_actions = (
      ('error', 'Number of tryjob verifier runs errored.'),
      ('fail', 'Number of tryjob verifier runs failed.'),
      ('pass', 'Number of tryjob verifier runs passed.'),
      ('retry', 'Number of tryjob verifier runs retried.'),
      ('skip', 'Number of tryjob verifier runs skipped.'),
      ('start', 'Number of tryjob verifier runs started.'),
      ('timeout', 'Number of tryjob verifier runs that timed out.'),
    )
    for action, description in counted_actions:
      self.analyze_records(
        (1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
        (2, {'issue': 1, 'patchset': 1, 'action': 'verifier_' + action}),
        (3, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
        (4, {'issue': 1, 'patchset': 2, 'action': 'patch_start'}),
        (5, {'issue': 1, 'patchset': 2, 'action': 'patch_stop'}),
        (6, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
        (7, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
      )
      name = 'tryjobverifier-%s-count' % action
      self.assertEquals(self.create_count(
          name=name,
          description=description,
          tally={PatchsetReference(1, 1): 1},
        ), self.get_stats(name))

  def test_tryjobverifier_first_run_durations(self):
    self.analyze_records(
      (1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
      (2, {'issue': 1, 'patchset': 1, 'action': 'verifier_start'}),
      (3, {'issue': 1, 'patchset': 1, 'action': 'verifier_retry'}),
      (4, {'issue': 1, 'patchset': 1, 'action': 'verifier_pass'}),
      (5, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
      (6, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
      (7, {'issue': 2, 'patchset': 1, 'action': 'verifier_start'}),
      (8, {'issue': 2, 'patchset': 1, 'action': 'verifier_timeout'}),
      (9, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
      (10, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
      (11, {'issue': 2, 'patchset': 1, 'action': 'verifier_start'}),
      (15, {'issue': 2, 'patchset': 1, 'action': 'verifier_fail'}),
      (16, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
      (17, {'issue': 3, 'patchset': 1, 'action': 'patch_start'}),
      (18, {'issue': 3, 'patchset': 1, 'action': 'verifier_start'}),
      (21, {'issue': 3, 'patchset': 1, 'action': 'verifier_pass'}),
      (22, {'issue': 3, 'patchset': 1, 'action': 'patch_stop'}),
    )
    self.assertEquals(self.create_list(
        name='tryjobverifier-first-run-durations',
        description='Time spent on each tryjob verifier first run.',
        unit='seconds',
        points=(
          (hours(1), PatchsetReference(1, 1)),
          (hours(1), PatchsetReference(2, 1)),
          (hours(4), PatchsetReference(2, 1)),
          (hours(3), PatchsetReference(3, 1)),
        ),
      ), self.get_stats('tryjobverifier-first-run-durations'))

  def test_tryjobverifier_retry_durations(self):
    self.analyze_records(
      (1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
      (2, {'issue': 1, 'patchset': 1, 'action': 'verifier_start'}),
      (3, {'issue': 1, 'patchset': 1, 'action': 'verifier_pass'}),
      (4, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
      (5, {'issue': 2, 'patchset': 1, 'action': 'patch_start'}),
      (6, {'issue': 2, 'patchset': 1, 'action': 'verifier_start'}),
      (7, {'issue': 2, 'patchset': 1, 'action': 'verifier_retry'}),
      (10, {'issue': 2, 'patchset': 1, 'action': 'verifier_pass'}),
      (11, {'issue': 2, 'patchset': 1, 'action': 'patch_stop'}),
      (12, {'issue': 3, 'patchset': 2, 'action': 'patch_start'}),
      (13, {'issue': 3, 'patchset': 2, 'action': 'verifier_start'}),
      (14, {'issue': 3, 'patchset': 2, 'action': 'verifier_retry'}),
      (15, {'issue': 3, 'patchset': 2, 'action': 'verifier_retry'}),
      (16, {'issue': 3, 'patchset': 2, 'action': 'verifier_timeout'}),
      (17, {'issue': 3, 'patchset': 2, 'action': 'patch_stop'}),
      (18, {'issue': 3, 'patchset': 2, 'action': 'patch_start'}),
      (19, {'issue': 3, 'patchset': 2, 'action': 'verifier_start'}),
      (20, {'issue': 3, 'patchset': 2, 'action': 'verifier_retry'}),
      (21, {'issue': 3, 'patchset': 2, 'action': 'verifier_retry'}),
      (22, {'issue': 3, 'patchset': 2, 'action': 'verifier_pass'}),
      (23, {'issue': 3, 'patchset': 2, 'action': 'patch_stop'}),
    )
    self.assertEquals(self.create_list(
        name='tryjobverifier-retry-durations',
        description='Time spent on each tryjob verifier retry.',
        unit='seconds',
        points=(
          (hours(3), PatchsetReference(2, 1)),
          (hours(1), PatchsetReference(3, 2)),
          (hours(1), PatchsetReference(3, 2)),
          (hours(1), PatchsetReference(3, 2)),
          (hours(1), PatchsetReference(3, 2)),
        ),
      ), self.get_stats('tryjobverifier-retry-durations'))

  def test_tryjobverifier_total_durations(self):
    self.analyze_records(
      (1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
      (2, {'issue': 1, 'patchset': 1, 'action': 'verifier_start'}),
      (3, {'issue': 1, 'patchset': 1, 'action': 'verifier_pass'}),
      (4, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
      (5, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
      (6, {'issue': 1, 'patchset': 1, 'action': 'verifier_start'}),
      (10, {'issue': 1, 'patchset': 1, 'action': 'verifier_fail'}),
      (11, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
      (12, {'issue': 1, 'patchset': 2, 'action': 'patch_start'}),
      (13, {'issue': 1, 'patchset': 2, 'action': 'verifier_start'}),
      (14, {'issue': 1, 'patchset': 2, 'action': 'verifier_retry'}),
      (20, {'issue': 1, 'patchset': 2, 'action': 'verifier_timeout'}),
      (21, {'issue': 1, 'patchset': 2, 'action': 'patch_stop'}),
    )
    self.assertEquals(self.create_list(
        name='tryjobverifier-total-durations',
        description='Total time spent per CQ attempt on tryjob verifier runs.',
        unit='seconds',
        points=(
          (hours(1), PatchsetReference(1, 1)),
          (hours(4), PatchsetReference(1, 1)),
          (hours(7), PatchsetReference(1, 2)),
        ),
      ), self.get_stats('tryjobverifier-total-durations'))
