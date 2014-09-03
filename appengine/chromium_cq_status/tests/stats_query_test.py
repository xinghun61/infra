# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta
import json

from testing_utils import testing

import main
from model.cq_stats import (
  CountStats,
  CQStats,
  ListStats,
)

class TestStatsQuery(testing.AppengineTestCase):
  app_module = main.app

  def test_query_headers(self):
    _clear_stats()
    response = self.test_app.get('/stats/query')
    self.assertEquals(response.headers['Access-Control-Allow-Origin'], '*')

  def test_query_empty(self):
    _clear_stats()
    response = self.test_app.get('/stats/query')
    self.assertEquals({
      'more': False,
      'results': [],
      'cursor': '',
    }, json.loads(response.body))

    _add_stats('project_a', 40, 789)
    _add_stats('project_b', 50, 1234)
    response = self.test_app.get('/stats/query')
    self.assertEquals({
      'more': False,
      'results': [{
        'project': 'project_a',
        'interval_days': 40,
        'begin': 789,
        'end': 3456789,
        'stats': [],
      }, {
        'project': 'project_b',
        'interval_days': 50,
        'begin': 1234,
        'end': 4321234,
        'stats': [],
      }],
    }, _parse_body(response))

  def test_query_project(self):
    _clear_stats()
    _add_stats('project_a', 40, 789)
    _add_stats('project_b', 40, 789)
    _add_stats('project_c', 40, 789)
    _add_stats('project_a', 50, 1234)
    _add_stats('project_b', 50, 1234)
    _add_stats('project_c', 50, 1234)
    response = self.test_app.get('/stats/query', params={
      'project': 'project_b',
    })
    self.assertEquals({
      'more': False,
      'results': [{
        'project': 'project_b',
        'interval_days': 40,
        'begin': 789,
        'end': 3456789,
        'stats': [],
      }, {
        'project': 'project_b',
        'interval_days': 50,
        'begin': 1234,
        'end': 4321234,
        'stats': [],
      }],
    }, _parse_body(response))

  def test_query_interval_days(self):
    _clear_stats()
    _add_stats('project_a', 20, 123)
    _add_stats('project_b', 30, 456)
    _add_stats('project_c', 40, 789)
    _add_stats('project_d', 50, 1234)
    response = self.test_app.get('/stats/query', params={
      'interval_days': 40,
    })
    self.assertEquals({
      'more': False,
      'results': [{
        'project': 'project_c',
        'interval_days': 40,
        'begin': 789,
        'end': 3456789,
        'stats': [],
      }],
    }, _parse_body(response))

  def test_query_begin(self):
    _clear_stats()
    _add_stats('project_a', 20, 123)
    _add_stats('project_b', 30, 456)
    _add_stats('project_c', 40, 789)
    _add_stats('project_d', 50, 1234)
    response = self.test_app.get('/stats/query', params={
      'begin': 500,
    })
    self.assertEquals({
      'more': False,
      'results': [{
        'project': 'project_c',
        'interval_days': 40,
        'begin': 789,
        'end': 3456789,
        'stats': [],
      }, {
        'project': 'project_d',
        'interval_days': 50,
        'begin': 1234,
        'end': 4321234,
        'stats': [],
      }],
    }, _parse_body(response))

  def test_query_end(self):
    _clear_stats()
    _add_stats('project_a', 40, 789)
    _add_stats('project_b', 50, 1234)
    response = self.test_app.get('/stats/query', params={
      'end': 1000,
    })
    self.assertEquals({
      'more': False,
      'results': [{
        'project': 'project_a',
        'interval_days': 40,
        'begin': 789,
        'end': 3456789,
        'stats': [],
      }],
    }, _parse_body(response))

  def test_query_names(self):
    _clear_stats()
    _add_stats('project_a', 40, 789, [
      CountStats(name='match_a', count=100),
      ListStats(name='match_b', unit='in'),
      CountStats(name='mismatch_a', description='', count=0),
    ])
    _add_stats('project_b', 50, 1234, [
      CountStats(name='match_a', count=200),
      ListStats(name='mismatch_b', unit=''),
    ])
    _add_stats('project_c', 60, 5678, [
      CountStats(name='mismatch_c', count=0),
      ListStats(name='mismatch_d', unit=''),
    ])
    response = self.test_app.get('/stats/query', params={
      'names': 'match_a,match_b',
    })
    self.assertEquals({
      'more': False,
      'results': [{
        'project': 'project_a',
        'interval_days': 40,
        'begin': 789,
        'end': 3456789,
        'stats': [{
          'type': 'count',
          'name': 'match_a',
          'description': '',
          'count': 100,
        }, {
          'type': 'list',
          'name': 'match_b',
          'description': '',
          'unit': 'in',
          'sample_size': 0,
          'min': 0,
          'max': 0,
          'mean': 0,
          'percentile_10': 0,
          'percentile_25': 0,
          'percentile_50': 0,
          'percentile_75': 0,
          'percentile_90': 0,
          'percentile_95': 0,
          'percentile_99': 0,
          'best_10': [],
          'worst_10': [],
        }],
      }, {
        'project': 'project_b',
        'interval_days': 50,
        'begin': 1234,
        'end': 4321234,
        'stats': [{
          'type': 'count',
          'name': 'match_a',
          'description': '',
          'count': 200,
        }],
      }],
    }, _parse_body(response))

  def test_query_count_cursor(self):
    _clear_stats()
    _add_stats('project_a', 1, 0)
    _add_stats('project_b', 1, 1)
    _add_stats('project_c', 1, 2)
    _add_stats('project_d', 1, 3)
    _add_stats('project_e', 1, 4)
    response = self.test_app.get('/stats/query', params={
      'count': 2,
    })
    self.assertEquals({
      'more': True,
      'results': [{
        'project': 'project_a',
        'interval_days': 1,
        'begin': 0,
        'end': 86400,
        'stats': [],
      }, {
        'project': 'project_b',
        'interval_days': 1,
        'begin': 1,
        'end': 86401,
        'stats': [],
      }],
    }, _parse_body(response))
    cursor = json.loads(response.body)['cursor']
    response = self.test_app.get('/stats/query', params={
      'count': 2,
      'cursor': cursor,
    })
    self.assertEquals({
      'more': True,
      'results': [{
        'project': 'project_c',
        'interval_days': 1,
        'begin': 2,
        'end': 86402,
        'stats': [],
      }, {
        'project': 'project_d',
        'interval_days': 1,
        'begin': 3,
        'end': 86403,
        'stats': [],
      }],
    }, _parse_body(response))
    cursor = json.loads(response.body)['cursor']
    response = self.test_app.get('/stats/query', params={
      'count': 2,
      'cursor': cursor,
    })
    self.assertEquals({
      'more': False,
      'results': [{
        'project': 'project_e',
        'interval_days': 1,
        'begin': 4,
        'end': 86404,
        'stats': [],
      }],
    }, _parse_body(response))

def _clear_stats(): # pragma: no cover
  for cq_stats in CQStats.query():
    cq_stats.key.delete()
  assert CQStats.query().count() == 0

def _add_stats(project, days, begin, stats_list=None): # pragma: no cover
  cq_stats = CQStats(
    project=project,
    interval_days=days,
    begin=datetime.utcfromtimestamp(begin),
    end=datetime.utcfromtimestamp(begin) + timedelta(days),
  )
  if stats_list:
    cq_stats.count_stats = [
        stats for stats in stats_list if type(stats) == CountStats]
    cq_stats.list_stats = [
        stats for stats in stats_list if type(stats) == ListStats]
  cq_stats.put()

def _parse_body(response, preserve_cursor=False): # pragma: no cover
  packet = json.loads(response.body)
  if not preserve_cursor:
    del packet['cursor']
  return packet
