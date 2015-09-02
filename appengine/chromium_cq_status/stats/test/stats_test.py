# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta

from tests.testing_utils import testing

import main
from model.record import Record
from model.cq_stats import CountStats, CQStats, ListStats
from shared.config import STATS_START_TIMESTAMP
from shared.config import TRYJOBVERIFIER
from shared.utils import minutes_per_day
from handlers import update_stats

stats_start = datetime.utcfromtimestamp(STATS_START_TIMESTAMP)
test_analysis_end = stats_start + timedelta(days=1)

class StatsTest(testing.AppengineTestCase):  # pragma: no cover
  '''Utility class for stats tests that want to load/clear test Record data.'''
  app_module = main.app

  def add_record(self, hours_from_start, tagged_fields):
    tagged_fields.setdefault('project', 'test')
    if tagged_fields.get('action', '').startswith('verifier_'):
      tagged_fields.setdefault('verifier', TRYJOBVERIFIER)
    self.mock_now(datetime.utcfromtimestamp(STATS_START_TIMESTAMP) +
        timedelta(hours=hours_from_start))
    Record(
      tags=['%s=%s' % (k, v) for k, v in tagged_fields.items()],
      fields=tagged_fields,
    ).put()

  def analyze_records(self, *record_params_list):
    self.clear_all()
    for record_params in record_params_list:
      self.add_record(*record_params)
    update_stats.update_missing_cq_stats(minutes_per_day, test_analysis_end)

  @staticmethod
  def clear_records():
    for record in Record.query():
      record.key.delete()
    assert Record.query().count() == 0

  @staticmethod
  def clear_cq_stats():
    for cq_stats in CQStats.query():
      cq_stats.key.delete()
    assert CQStats.query().count() == 0

  def clear_all(self):
    self.clear_records()
    self.clear_cq_stats()

  @staticmethod
  def create_count(name, description, tally):
    count_stats = CountStats(
      name=name,
      description=description,
    )
    count_stats.set_from_tally(tally)
    # Force JSON properties to get serialised
    count_stats.put()
    # Hide key for equality comparison
    count_stats.key = None
    return count_stats

  @staticmethod
  def create_list(name, description, unit, points):
    list_stats = ListStats(
      name=name,
      description=description,
      unit=unit,
    )
    list_stats.set_from_points(points)
    # Same hacks here as create_count().
    list_stats.put()
    list_stats.key = None
    return list_stats

  @staticmethod
  def get_stats(name):
    cq_stats = CQStats.query(CQStats.begin == stats_start).get()
    for stats in cq_stats.count_stats + cq_stats.list_stats:
      if stats.name == name:
        return stats
    return None

def hours(n): # pragma: no cover
  '''Convert hours to seconds.'''
  return n * 60 * 60
