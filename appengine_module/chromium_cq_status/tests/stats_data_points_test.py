# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json

from appengine_module.testing_utils import testing

from appengine_module.chromium_cq_status import main
from appengine_module.chromium_cq_status.model.cq_stats import (
  CQStats,
  ListStats,
)

class TestStatsDataPoints(testing.AppengineTestCase):
  app_module = main.app
  maxDiff = None

  def test_best_data_points(self):
    key = _reset_stats()
    response = self.test_app.get('/stats/best/test_name/%s' % key)
    self.assertEquals(response.headers['Access-Control-Allow-Origin'], '*')
    self.assertEquals([
      [0, {'data_point': 'a'}],
      [1, {'data_point': 'b'}],
      [2, {'data_point': 'c'}],
    ], json.loads(response.body))

  def test_worst_data_points(self):
    key = _reset_stats()
    response = self.test_app.get('/stats/worst/test_name/%s' % key)
    self.assertEquals(response.headers['Access-Control-Allow-Origin'], '*')
    self.assertEquals([
      [2, {'data_point': 'c'}],
      [1, {'data_point': 'b'}],
      [0, {'data_point': 'a'}],
    ], json.loads(response.body))

def _reset_stats(): # pragma: no cover
  for cq_stats in CQStats.query():
    cq_stats.key.delete()
  assert CQStats.query().count() == 0
  cq_stats = CQStats(
    project='test',
    interval_minutes=1,
    begin=datetime.utcfromtimestamp(0),
    end=datetime.utcfromtimestamp(1),
    count_stats=[],
    list_stats=[
      ListStats(
        name='test_name',
        description='test_description',
        unit='test_unit',
        best_100=[
          [0, {'data_point': 'a'}],
          [1, {'data_point': 'b'}],
          [2, {'data_point': 'c'}],
        ],
        worst_100=[
          [2, {'data_point': 'c'}],
          [1, {'data_point': 'b'}],
          [0, {'data_point': 'a'}],
        ],
      )
    ]
  ).put()
  return cq_stats.id()
