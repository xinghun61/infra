#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from tests.testing_utils import testing

import main
from model.cq_stats import (
  CountStats,
  ListStats,
  CQStats,
)
from stats.analysis import (
  intervals_in_range,
  update_cq_stats,
  update_stats_list,
)

class TestAnalysis(testing.AppengineTestCase):
  app_module = main.app

  def test_intervals_in_range(self):
    self.assertEqual([
        (datetime(2000, 1, 1, 10), datetime(2000, 1, 1, 11)),
        (datetime(2000, 1, 1, 11), datetime(2000, 1, 1, 12)),
        (datetime(2000, 1, 1, 12), datetime(2000, 1, 1, 13)),
        (datetime(2000, 1, 1, 13), datetime(2000, 1, 1, 14)),
      ], intervals_in_range(60,
          datetime(2000, 1, 1, 10), datetime(2000, 1, 1, 14)))

    self.assertEqual([
        (datetime(2000, 1, 1, 8), datetime(2000, 1, 2, 8)),
        (datetime(2000, 1, 2, 8), datetime(2000, 1, 3, 8)),
        (datetime(2000, 1, 3, 8), datetime(2000, 1, 4, 8)),
      ], intervals_in_range(1440,
          datetime(2000, 1, 1), datetime(2000, 1, 5)))

    self.assertEqual([], intervals_in_range(1440,
        datetime(2000, 1, 1, 8), datetime(2000, 1, 1, 9)))

  def test_update_cq_stats_empty(self):
    _clear_cq_stats()
    update_cq_stats({}, 60, datetime(2000, 1, 1, 1), datetime(2000, 1, 1, 2))
    self.assertEqual(0, CQStats.query().count())

  def test_update_cq_stats_create(self):
    _clear_cq_stats()
    update_cq_stats({
        'test-project': [
          CountStats(
            name='test-count',
            description='test-count-description',
            count=123),
          ListStats(
            name='test-list',
            description='test-list-description',
            unit='test-unit'),
        ],
      }, 60, datetime(2000, 1, 1, 1), datetime(2000, 1, 1, 2))
    self.assertEqual(1, CQStats.query().count())
    cq_stats = CQStats.query().get()
    self.assertEqual('test-project', cq_stats.project)
    self.assertEqual(60, cq_stats.interval_minutes)
    self.assertEqual(datetime(2000, 1, 1, 1), cq_stats.begin)
    self.assertEqual(datetime(2000, 1, 1, 2), cq_stats.end)
    self.assertEqual([
        CountStats(
          name='test-count',
          description='test-count-description',
          count=123),
      ], cq_stats.count_stats)
    self.assertEqual([
        ListStats(
          name='test-list',
          description='test-list-description',
          unit='test-unit'),
      ], cq_stats.list_stats)

  def test_update_cq_stats_modify(self):
    _clear_cq_stats()
    CQStats(
      project='test-project',
      interval_minutes=60,
      begin=datetime(2000, 1, 1, 1),
      end=datetime(2000, 1, 1, 2),
      count_stats=[
        CountStats(
          name='test-count',
          description='test-count-description',
          count=123),
      ],
      list_stats=[
        ListStats(
          name='test-list',
          description='test-list-description',
          unit='test-unit'),
      ],
    ).put()
    self.assertEqual(1, CQStats.query().count())
    update_cq_stats({
        'test-project': [
          CountStats(
            name='test-count',
            description='test-count-description',
            count=456),
        ],
      }, 60, datetime(2000, 1, 1, 1), datetime(2000, 1, 1, 2))
    self.assertEqual(1, CQStats.query().count())
    cq_stats = CQStats.query().get()
    self.assertEqual('test-project', cq_stats.project)
    self.assertEqual(60, cq_stats.interval_minutes)
    self.assertEqual(datetime(2000, 1, 1, 1), cq_stats.begin)
    self.assertEqual(datetime(2000, 1, 1, 2), cq_stats.end)
    self.assertEqual([
        CountStats(
          name='test-count',
          description='test-count-description',
          count=456),
      ], cq_stats.count_stats)
    self.assertEqual([
        ListStats(
          name='test-list',
          description='test-list-description',
          unit='test-unit'),
      ], cq_stats.list_stats)

  def test_update_stats_list_empty(self):
    test_list = [
      CountStats(name='a', description='a', count=1),
      CountStats(name='b', description='b', count=2),
    ]
    update_stats_list(test_list, {})
    self.assertEqual([
      CountStats(name='a', description='a', count=1),
      CountStats(name='b', description='b', count=2),
    ], test_list)

  def test_update_stats_list_add(self):
    test_list = [
      CountStats(name='a', description='a', count=1),
      CountStats(name='b', description='b', count=2),
    ]
    update_stats_list(test_list, {
      'c': CountStats(name='c', description='c', count=3),
      'd': CountStats(name='d', description='d', count=4),
    })
    self.assertEqual([
      CountStats(name='a', description='a', count=1),
      CountStats(name='b', description='b', count=2),
      CountStats(name='c', description='c', count=3),
      CountStats(name='d', description='d', count=4),
    ], test_list)

  def test_update_stats_list_replace(self):
    test_list = [
      CountStats(name='a', description='a', count=1),
      CountStats(name='b', description='b', count=2),
    ]
    update_stats_list(test_list, {
      'a': CountStats(name='a', description='a', count=10),
      'b': CountStats(name='b', description='b', count=20),
    })
    self.assertEqual([
      CountStats(name='a', description='a', count=10),
      CountStats(name='b', description='b', count=20),
    ], test_list)

  def test_update_stats_list_mixed(self):
    test_list = [
      CountStats(name='a', description='a', count=1),
      CountStats(name='b', description='b', count=2),
    ]
    update_stats_list(test_list, {
      'b': CountStats(name='b', description='b', count=20),
      'c': CountStats(name='c', description='c', count=3),
    })
    self.assertEqual([
      CountStats(name='a', description='a', count=1),
      CountStats(name='b', description='b', count=20),
      CountStats(name='c', description='c', count=3),
    ], test_list)

def _clear_cq_stats(): # pragma: no cover
  for cq_stats in CQStats.query():
    cq_stats.key.delete()
  assert CQStats.query().count() == 0
