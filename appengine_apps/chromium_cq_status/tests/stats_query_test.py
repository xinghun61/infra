# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta
import json

from tests.testing_utils import testing

import highend
from model.cq_stats import (
  CountStats,
  CQStats,
  ListStats,
)
from shared.utils import minutes_per_day

class TestStatsQuery(testing.AppengineTestCase):
  app_module = highend.app
  maxDiff = None

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
        'project': 'project_b',
        'interval_minutes': 50 * minutes_per_day,
        'begin': 1234,
        'end': 4321234,
        'stats': [],
      }, {
        'project': 'project_a',
        'interval_minutes': 40 * minutes_per_day,
        'begin': 789,
        'end': 3456789,
        'stats': [],
      }],
    }, _parse_body(response))

  def test_query_key(self):
    _clear_stats()
    key_a = _add_stats('project_a', 50, 1234).key.id()
    key_b = _add_stats('project_b', 40, 789).key.id()

    response = self.test_app.get('/stats/query', params={
      'key': key_a,
    })
    self.assertEquals({
      'more': False,
      'results': [{
        'project': 'project_a',
        'interval_minutes': 50 * minutes_per_day,
        'begin': 1234,
        'end': 4321234,
        'stats': [],
      }],
    }, _parse_body(response))

    response = self.test_app.get('/stats/query', params={
      'key': key_b,
    })
    self.assertEquals({
      'more': False,
      'results': [{
        'project': 'project_b',
        'interval_minutes': 40 * minutes_per_day,
        'begin': 789,
        'end': 3456789,
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
        'interval_minutes': 50 * minutes_per_day,
        'begin': 1234,
        'end': 4321234,
        'stats': [],
      }, {
        'project': 'project_b',
        'interval_minutes': 40 * minutes_per_day,
        'begin': 789,
        'end': 3456789,
        'stats': [],
      }],
    }, _parse_body(response))

  def test_query_interval_minutes(self):
    _clear_stats()
    _add_stats('project_a', 20, 123)
    _add_stats('project_b', 30, 456)
    _add_stats('project_c', 40, 789)
    _add_stats('project_d', 50, 1234)
    response = self.test_app.get('/stats/query', params={
      'interval_minutes': 40 * minutes_per_day,
    })
    self.assertEquals({
      'more': False,
      'results': [{
        'project': 'project_c',
        'interval_minutes': 40 * minutes_per_day,
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
        'project': 'project_d',
        'interval_minutes': 50 * minutes_per_day,
        'begin': 1234,
        'end': 4321234,
        'stats': [],
      }, {
        'project': 'project_c',
        'interval_minutes': 40 * minutes_per_day,
        'begin': 789,
        'end': 3456789,
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
        'interval_minutes': 40 * minutes_per_day,
        'begin': 789,
        'end': 3456789,
        'stats': [],
      }],
    }, _parse_body(response))

  def test_query_names(self):  # pragma: no cover
    _clear_stats()
    _add_stats('project_a', 40, 789, [
      CountStats(name='match_a', description='', count=100),
      ListStats(name='match_b', description='', unit='in'),
      CountStats(name='mismatch_a', description='', count=0),
    ])
    _add_stats('project_b', 50, 1234, [
      CountStats(name='match_a', description='', count=200),
      ListStats(name='mismatch_b', description='', unit=''),
    ])
    _add_stats('project_c', 60, 5678, [
      CountStats(name='mismatch_c', description='', count=0),
      ListStats(name='mismatch_d', description='', unit=''),
    ])
    expectation = {
      'more': False,
      'results': [{
        'project': 'project_b',
        'interval_minutes': 50 * minutes_per_day,
        'begin': 1234,
        'end': 4321234,
        'stats': [{
          'type': 'count',
          'name': 'match_a',
          'description': '',
          'count': 200,
        }],
      }, {
        'project': 'project_a',
        'interval_minutes': 40 * minutes_per_day,
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
        }],
      }],
    }

    response = self.test_app.get('/stats/query', params={
      'names': 'match_a,match_b',
    })
    self.assertEquals(expectation, _parse_body(response))

    response = self.test_app.get('/stats/query', params={
      'names': 'match_*',
    })
    self.assertEquals(expectation, _parse_body(response))

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
        'project': 'project_e',
        'interval_minutes': 1 * minutes_per_day,
        'begin': 4,
        'end': 86404,
        'stats': [],
      }, {
        'project': 'project_d',
        'interval_minutes': 1 * minutes_per_day,
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
      'more': True,
      'results': [{
        'project': 'project_c',
        'interval_minutes': 1 * minutes_per_day,
        'begin': 2,
        'end': 86402,
        'stats': [],
      }, {
        'project': 'project_b',
        'interval_minutes': 1 * minutes_per_day,
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
      'more': False,
      'results': [{
        'project': 'project_a',
        'interval_minutes': 1 * minutes_per_day,
        'begin': 0,
        'end': 86400,
        'stats': [],
      }],
    }, _parse_body(response))

def _clear_stats(): # pragma: no cover
  for cq_stats in CQStats.query():
    cq_stats.key.delete()
  assert CQStats.query().count() == 0

def _add_stats(project, days, begin, stats_list=None): # pragma: no cover
  minutes = days * minutes_per_day
  cq_stats = CQStats(
    project=project,
    interval_minutes=minutes,
    begin=datetime.utcfromtimestamp(begin),
    end=datetime.utcfromtimestamp(begin) + timedelta(minutes=minutes),
  )
  if stats_list:
    cq_stats.count_stats = [
        stats for stats in stats_list if type(stats) == CountStats]
    cq_stats.list_stats = [
        stats for stats in stats_list if type(stats) == ListStats]
  cq_stats.put()
  return cq_stats

def _parse_body(response, preserve_cursor=False): # pragma: no cover
  packet = json.loads(response.body)
  if not preserve_cursor:
    del packet['cursor']
  for cq_stats in packet['results']:
    del cq_stats['key']
  return packet
