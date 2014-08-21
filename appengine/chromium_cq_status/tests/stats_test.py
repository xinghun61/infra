# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta
import os
import sys

# App Engine source file imports must be relative to their app's root.
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from appengine.utils import testing
from appengine.chromium_cq_status import main
from appengine.chromium_cq_status.cron import cq_stats
from appengine.chromium_cq_status.model.cq_stats import CQStats, NumberListStats
from appengine.chromium_cq_status.model.record import Record

class TestStats(testing.AppengineTestCase):
  app_module = main.app

  def setUp(self):
    super(TestStats, self).setUp()
    self.mock_current_user(is_admin=True)
    for record in Record.query():
      record.key.delete()
    assert Record.query().count() == 0
    for stats in CQStats.query():
      stats.key.delete()
    assert CQStats.query().count() == 0

  def tearDown(self):
    super(TestStats, self).tearDown()
    cq_stats.utcnow_for_testing = None

  def test_daily_stats(self):
    start = datetime(1970, 1, 13) + timedelta(hours=8)
    # First day
    self._add_record(1, 1, start, 'initial')
    self._add_record(1, 1, start + timedelta(0, 100), 'commit')

    self._add_record(2, 1, start + timedelta(1, -100), 'initial')

    # Second day
    self._add_record(2, 1, start + timedelta(1, 100), 'abort')

    self._add_record(3, 1, start + timedelta(1, 200), 'initial')
    self._add_record(3, 1, start + timedelta(1, 300), 'abort')

    # Third day
    self._add_record(3, 1, start + timedelta(2, 100), 'initial')
    self._add_record(3, 1, start + timedelta(2, 200), 'abort')
    self._add_record(3, 1, start + timedelta(2, 300), 'initial')
    self._add_record(3, 1, start + timedelta(2, 500), 'commit')

    self._add_record(4, 1, start + timedelta(2, 500), 'initial')
    self._add_record(4, 1, start + timedelta(2, 600), 'abort')

    self._add_record(4, 2, start + timedelta(2, 700), 'initial')
    self._add_record(4, 2, start + timedelta(2, 850), 'commit')

    self._add_record(5, 1, start + timedelta(2, 900), 'initial')

    cq_stats.utcnow_for_testing = start + timedelta(3, 1)
    cq_stats.analyze_interval(days=1)
    self._assertStats([
      CQStats(
        interval_days=1,
        begin=start,
        end=start + timedelta(1),
        project=u'test',
        patchset_count=1,
        patchset_success_count=1,
        patchset_run_counts=NumberListStats.from_list([1]),
        patchset_false_rejections=NumberListStats.from_list([0]),
        run_count=1,
        run_success_count=1,
        run_seconds=NumberListStats.from_list([100]),
      ),
      CQStats(
        interval_days=1,
        begin=start + timedelta(1),
        end=start + timedelta(2),
        project=u'test',
        patchset_count=2,
        patchset_success_count=0,
        patchset_run_counts=NumberListStats.from_list([1, 1]),
        patchset_false_rejections=NumberListStats.from_list([0, 0]),
        run_count=2,
        run_success_count=0,
        run_seconds=NumberListStats.from_list([200, 100]),
      ),
      CQStats(
        interval_days=1,
        begin=start + timedelta(2),
        end=start + timedelta(3),
        project=u'test',
        patchset_count=3,
        patchset_success_count=2,
        patchset_run_counts=NumberListStats.from_list([2, 1, 1]),
        patchset_false_rejections=NumberListStats.from_list([1, 0, 0]),
        run_count=4,
        run_success_count=2,
        run_seconds=NumberListStats.from_list([100, 200, 100, 150]),
      ),
    ])

  def test_project_separation(self):
    start = datetime(1970, 1, 13) + timedelta(hours=8)
    self._add_record(1, 1, start, 'initial', 'project_a')
    self._add_record(1, 1, start + timedelta(0, 100), 'commit', 'project_a')
    self._add_record(2, 1, start, 'initial', 'project_b')
    self._add_record(2, 1, start + timedelta(0, 200), 'abort', 'project_b')

    cq_stats.utcnow_for_testing = start + timedelta(1, 1)
    cq_stats.analyze_interval(days=1)
    self._assertStats([
      CQStats(
        interval_days=1,
        begin=start,
        end=start + timedelta(1),
        project=u'project_b',
        patchset_count=1,
        patchset_success_count=0,
        patchset_run_counts=NumberListStats.from_list([1]),
        patchset_false_rejections=NumberListStats.from_list([0]),
        run_count=1,
        run_success_count=0,
        run_seconds=NumberListStats.from_list([200]),
      ),
      CQStats(
        interval_days=1,
        begin=start,
        end=start + timedelta(1),
        project=u'project_a',
        patchset_count=1,
        patchset_success_count=1,
        patchset_run_counts=NumberListStats.from_list([1]),
        patchset_false_rejections=NumberListStats.from_list([0]),
        run_count=1,
        run_success_count=1,
        run_seconds=NumberListStats.from_list([100]),
      ),
    ])

  def _add_record(self, issue, patchset, timestamp, verification,
      project='test'):
    self.mock_now(timestamp)
    Record(
      tags=[
        'issue=%s' % issue,
        'patchset=%s' % patchset,
        'verification=%s' % verification
      ],
      fields={
        'project': project,
        'issue': issue,
        'patchset': patchset,
        'verification': verification,
      },
    ).put()

  def _assertStats(self, expected_stats, actual_stats=None):
    if not actual_stats:
      actual_stats = list(CQStats.query().order(CQStats.begin))
    self.assertEquals(len(expected_stats), len(actual_stats))
    oldMaxDiff = self.maxDiff
    self.maxDiff = None
    for i in range(len(expected_stats)):
      expected = expected_stats[i]
      actual = actual_stats[i]
      actual.key = None
      self.assertEquals(expected, actual)
    self.maxDiff = oldMaxDiff

