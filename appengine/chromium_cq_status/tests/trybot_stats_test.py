# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# StatsTest must be imported first in order to get proper ndb monkeypatching.
from tests.stats_test import StatsTest
from stats.analysis import PatchsetReference
from stats.trybot_stats import TrybotReference

passed = 0
failed = 1
running = 2

class TrybotStatsTest(StatsTest):
  trybot_records = (
    (1, {'issue': 1, 'patchset': 1, 'action': 'patch_start'}),
    (2, {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
      'jobs': {
        'test_master_a': {
          'test_builder_ppp': {'status': running},
          'test_builder_fff': {'status': running},
        },
        'test_master_b': {
          'test_builder_ffp': {'status': running},
        },
      },
    }),

    (3, {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
      'jobs': {'test_master_a': {'test_builder_ppp': {'status': passed}}}}),
    (4, {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
      'jobs': {'test_master_a': {'test_builder_ppp': {'status': passed}}}}),
    (5, {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
      'jobs': {'test_master_a': {'test_builder_ppp': {'status': passed}}}}),

    (6, {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
      'jobs': {'test_master_a': {'test_builder_fff': {'status': failed}}}}),
    (7, {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
      'jobs': {'test_master_a': {'test_builder_fff': {'status': failed}}}}),
    (8, {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
      'jobs': {'test_master_a': {'test_builder_fff': {'status': failed}}}}),

    (9, {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
      'jobs': {'test_master_b': {'test_builder_ffp': {'status': failed}}}}),
    (10, {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
      'jobs': {'test_master_b': {'test_builder_ffp': {'status': failed}}}}),
    (11, {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
      'jobs': {'test_master_b': {'test_builder_ffp': {'status': passed}}}}),
    (12, {'issue': 1, 'patchset': 1, 'action': 'patch_stop'}),
  )

  def test_trybot_false_reject_count(self):
    self.analyze_records(*self.trybot_records)
    self.assertEquals(self.create_count(
        name='trybot-test_builder_ppp-false-reject-count',
        description=('Number of false rejects by the test_builder_ppp trybot. '
                     'This counts any failed runs that also had passing runs '
                     'on the same patch.'),
        tally={PatchsetReference(1, 1): 0},
      ), self.get_stats('trybot-test_builder_ppp-false-reject-count'))
    self.assertEquals(self.create_count(
        name='trybot-test_builder_fff-false-reject-count',
        description=('Number of false rejects by the test_builder_fff trybot. '
                     'This counts any failed runs that also had passing runs '
                     'on the same patch.'),
        tally={PatchsetReference(1, 1): 0},
      ), self.get_stats('trybot-test_builder_fff-false-reject-count'))
    self.assertEquals(self.create_count(
        name='trybot-test_builder_ffp-false-reject-count',
        description=('Number of false rejects by the test_builder_ffp trybot. '
                     'This counts any failed runs that also had passing runs '
                     'on the same patch.'),
        tally={PatchsetReference(1, 1): 2},
      ), self.get_stats('trybot-test_builder_ffp-false-reject-count'))
    self.assertEquals(self.create_count(
        name='trybot-false-reject-count',
        description=('Number of false rejects across all trybots. '
                     'This counts any failed runs that also had passing runs '
                     'on the same patch.'),
        tally={TrybotReference('test_master_b', 'test_builder_ffp'): 2},
      ), self.get_stats('trybot-false-reject-count'))

  def test_trybot_failed_run_count(self):
    self.analyze_records(*self.trybot_records)
    self.assertEquals(self.create_count(
        name='trybot-test_builder_ppp-fail-count',
        description = 'Number of failing runs by the test_builder_ppp trybot.',
        tally={PatchsetReference(1, 1): 0},
      ), self.get_stats('trybot-test_builder_ppp-fail-count'))
    self.assertEquals(self.create_count(
        name='trybot-test_builder_fff-fail-count',
        description = 'Number of failing runs by the test_builder_fff trybot.',
        tally={PatchsetReference(1, 1): 3},
      ), self.get_stats('trybot-test_builder_fff-fail-count'))
    self.assertEquals(self.create_count(
        name='trybot-test_builder_ffp-fail-count',
        description = 'Number of failing runs by the test_builder_ffp trybot.',
        tally={PatchsetReference(1, 1): 2},
      ), self.get_stats('trybot-test_builder_ffp-fail-count'))
    self.assertEquals(self.create_count(
        name='trybot-fail-count',
        description = 'Number of failing runs across all trybots.',
        tally={
          TrybotReference('test_master_a', 'test_builder_ppp'): 0,
          TrybotReference('test_master_a', 'test_builder_fff'): 3,
          TrybotReference('test_master_b', 'test_builder_ffp'): 2,
        },
      ), self.get_stats('trybot-fail-count'))

  def test_trybot_successful_run_count(self):
    self.analyze_records(*self.trybot_records)
    self.assertEquals(self.create_count(
        name='trybot-test_builder_ppp-pass-count',
        description = 'Number of passing runs by the test_builder_ppp trybot.',
        tally={PatchsetReference(1, 1): 3},
      ), self.get_stats('trybot-test_builder_ppp-pass-count'))
    self.assertEquals(self.create_count(
        name='trybot-test_builder_fff-pass-count',
        description = 'Number of passing runs by the test_builder_fff trybot.',
        tally={PatchsetReference(1, 1): 0},
      ), self.get_stats('trybot-test_builder_fff-pass-count'))
    self.assertEquals(self.create_count(
        name='trybot-test_builder_ffp-pass-count',
        description = 'Number of passing runs by the test_builder_ffp trybot.',
        tally={PatchsetReference(1, 1): 1},
      ), self.get_stats('trybot-test_builder_ffp-pass-count'))
    self.assertEquals(self.create_count(
        name='trybot-pass-count',
        description = 'Number of passing runs across all trybots.',
        tally={
          TrybotReference('test_master_a', 'test_builder_ppp'): 3,
          TrybotReference('test_master_a', 'test_builder_fff'): 0,
          TrybotReference('test_master_b', 'test_builder_ffp'): 1,
        },
      ), self.get_stats('trybot-pass-count'))
