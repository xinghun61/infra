# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta

from appengine_module.testing_utils import testing

from appengine_module.chromium_cq_status import main
from appengine_module.chromium_cq_status.model.record import Record
from appengine_module.chromium_cq_status.model.cq_stats import CQStats
from appengine_module.chromium_cq_status.shared.config import STATS_START_TIMESTAMP  # pylint: disable=C0301
from appengine_module.chromium_cq_status.shared.utils import minutes_per_day  # pylint: disable=C0301
from appengine_module.chromium_cq_status.stats import analysis

class StatsTest(testing.AppengineTestCase): # pragma: no cover
  '''Utility class for stats tests that want to load/clear test Record data.'''
  app_module = main.app

  def add_record(self, hours_from_start, tagged_fields):
    tagged_fields.setdefault('project', 'test')
    if tagged_fields.get('action', '').startswith('verifier_'):
      tagged_fields.setdefault('verifier', 'simple try job')
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
    self.set_last_stats_day(1)
    analysis.analyze_interval(minutes_per_day)

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
  def set_last_stats_day(days_from_start):
    analysis.utcnow_for_testing = (
        datetime.utcfromtimestamp(STATS_START_TIMESTAMP) +
        timedelta(days=days_from_start))

  @staticmethod
  def get_stats(name):
    assert CQStats.query().count() == 1
    cq_stats = CQStats.query().get()
    for stats in cq_stats.count_stats + cq_stats.list_stats:
      if stats.name == name:
        return stats
    return None

def hours(n): # pragma: no cover
  '''Convert hours to seconds.'''
  return n * 60 * 60
