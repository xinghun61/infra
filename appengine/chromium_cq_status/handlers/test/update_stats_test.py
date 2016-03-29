#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from third_party.testing_utils import testing

import highend
from model.cq_stats import CQStats
from model.record import Record
from handlers.update_stats import missing_intervals

class TestUpdateStats(testing.AppengineTestCase):
  app_module = highend.app

  def setUp(self):
    super(TestUpdateStats, self).setUp()
    _clear_ndb()

  def test_missing_intervals_empty(self):
    self.mock_current_user(is_admin=True)
    self.assertEqual([], missing_intervals(60, datetime(2000, 1, 1)))
    # Smoke test for coverage.
    self.test_app.get('/background/update-stats?interval_minutes=1440')

  def test_missing_intervals_records_only(self):
    self.mock_now(datetime(2000, 1, 2, 0))
    Record().put()
    self.mock_now(datetime(2000, 1, 3, 0))
    Record().put()
    self.assertEqual([
      (datetime(2000, 1, 1, 8), datetime(2000, 1, 2, 8)),
      (datetime(2000, 1, 2, 8), datetime(2000, 1, 3, 8)),
    ], missing_intervals(1440, datetime(2000, 1, 4, 0)))

  def test_missing_intervals_mismatched_cq_stats(self):
    CQStats(
      project='',
      interval_minutes=60,
      begin=datetime(2000, 1, 3, 7),
      end=datetime(2000, 1, 3, 8)).put()
    self.mock_now(datetime(2000, 1, 2, 0))
    Record().put()
    self.assertEqual([
      (datetime(2000, 1, 1, 8), datetime(2000, 1, 2, 8)),
      (datetime(2000, 1, 2, 8), datetime(2000, 1, 3, 8)),
    ], missing_intervals(1440, datetime(2000, 1, 4, 0)))

  def test_missing_intervals_matched_cq_stats(self):
    CQStats(
      project='',
      interval_minutes=1440,
      begin=datetime(2000, 1, 2, 8),
      end=datetime(2000, 1, 3, 8)).put()
    self.assertEqual([
      (datetime(2000, 1, 3, 8), datetime(2000, 1, 4, 8)),
    ], missing_intervals(1440, datetime(2000, 1, 4, 8)))

def _clear_ndb(): # pragma: no cover
  for cq_stats in CQStats.query():
    cq_stats.key.delete()
  assert CQStats.query().count() == 0
  for record in Record.query():
    record.key.delete()
  assert Record.query().count() == 0
