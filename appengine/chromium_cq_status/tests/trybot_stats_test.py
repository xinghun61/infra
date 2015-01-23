# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# StatsTest must be imported first in order to get proper ndb monkeypatching.
from tests.stats_test import StatsTest
from stats.analysis import PatchsetReference
from stats.trybot_stats import TrybotReference

passed = 'JOB_SUCCEEDED'
failed = 'JOB_FAILED'
running = 'JOB_RUNNING'


test_builder_ppp = {
    'master': 'test_master_a',
    'builder': 'test_builder_ppp',
    'url': 'ppp',
}


test_builder_fff = {
    'master': 'test_master_a',
    'builder': 'test_builder_fff',
    'url': 'fff',
}


test_builder_ffp = {
    'master': 'test_master_b',
    'builder': 'test_builder_ffp',
    'url': 'ffp',
}


class TrybotStatsTest(StatsTest):
  # Keep this shorter than 24 records. Each record adds an hour of
  # virtual time, and the tests aggregate over a day.
  trybot_records = list(enumerate([
      {'issue': 1, 'patchset': 1, 'action': 'patch_start'},
      {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
        'jobs': {
          running: [test_builder_ppp, test_builder_fff, test_builder_ffp]
        },
      },

      {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
       'jobs': {
         passed: [test_builder_ppp],
         failed: [test_builder_fff, test_builder_ffp],
       },
      },

      {'issue': 1, 'patchset': 1, 'action': 'patch_stop'},
      {'issue': 1, 'patchset': 1, 'action': 'patch_start'},

      {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
       'jobs': {
         passed: [test_builder_ppp],
         failed: [test_builder_fff],
        },
      },
      {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
       'jobs': {
         failed: [test_builder_ffp, test_builder_fff],
         passed: [test_builder_ppp],
        },
      },

      {'issue': 1, 'patchset': 1, 'action': 'patch_stop'},
      {'issue': 1, 'patchset': 1, 'action': 'patch_start'},

      {'issue': 1, 'patchset': 1, 'action': 'verifier_jobs_update',
       'jobs': {
         passed: [test_builder_ppp],
         failed: [test_builder_fff],
         passed: [test_builder_ffp],
       },
      },

      {'issue': 1, 'patchset': 1, 'action': 'patch_stop'},
    ]))

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
        tally={PatchsetReference(1, 1): 1},
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
          TrybotReference('test_master_a', 'test_builder_ppp'): 1,
          TrybotReference('test_master_a', 'test_builder_fff'): 0,
          TrybotReference('test_master_b', 'test_builder_ffp'): 1,
        },
      ), self.get_stats('trybot-pass-count'))
