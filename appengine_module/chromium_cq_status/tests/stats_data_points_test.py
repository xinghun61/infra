# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json

from appengine_module.testing_utils import testing

from appengine_module.chromium_cq_status import main
from appengine_module.chromium_cq_status.model.cq_stats import (
  CountStats,
  CQStats,
  ListStats,
)

class TestStatsDataPoints(testing.AppengineTestCase):
  app_module = main.app
  maxDiff = None

  def test_lowest_count_data_points(self):
    key = _reset_stats()
    response = self.test_app.get('/stats/lowest/test-count/%s' % key)
    self.assertEquals(response.headers['Access-Control-Allow-Origin'], '*')
    self.assertEquals([
      [0, {'data_point': 'a'}],
      [1, {'data_point': 'b'}],
      [2, {'data_point': 'c'}],
    ], json.loads(response.body))

  def test_highest_count_data_points(self):
    key = _reset_stats()
    response = self.test_app.get('/stats/highest/test-count/%s' % key)
    self.assertEquals(response.headers['Access-Control-Allow-Origin'], '*')
    self.assertEquals([
      [2, {'data_point': 'c'}],
      [1, {'data_point': 'b'}],
      [0, {'data_point': 'a'}],
    ], json.loads(response.body))

  def test_lowest_list_data_points(self):
    key = _reset_stats()
    response = self.test_app.get('/stats/lowest/test-list/%s' % key)
    self.assertEquals(response.headers['Access-Control-Allow-Origin'], '*')
    self.assertEquals([
      [0, {'data_point': 'a'}],
      [1, {'data_point': 'b'}],
      [2, {'data_point': 'c'}],
    ], json.loads(response.body))

  def test_highest_list_data_points(self):
    key = _reset_stats()
    response = self.test_app.get('/stats/highest/test-list/%s' % key)
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
    count_stats=[
      CountStats(
        name='test-count',
        description='Test count description',
        count=3,
        highest_100=[
          [2, {'data_point': 'c'}],
          [1, {'data_point': 'b'}],
          [0, {'data_point': 'a'}],
        ],
        lowest_100=[
          [0, {'data_point': 'a'}],
          [1, {'data_point': 'b'}],
          [2, {'data_point': 'c'}],
        ],
      ),
    ],
    list_stats=[
      ListStats(
        name='test-list',
        description='Test list description',
        unit='test_unit',
        highest_100=[
          [2, {'data_point': 'c'}],
          [1, {'data_point': 'b'}],
          [0, {'data_point': 'a'}],
        ],
        lowest_100=[
          [0, {'data_point': 'a'}],
          [1, {'data_point': 'b'}],
          [2, {'data_point': 'c'}],
        ],
      ),
    ],
  ).put()
  return cq_stats.id()
