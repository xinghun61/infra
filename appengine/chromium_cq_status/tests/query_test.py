# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import os
import sys

# App Engine source file imports must be relative to their app's root.
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from appengine.utils import testing
from appengine.chromium_cq_status import main
from appengine.chromium_cq_status.model.record import Record

class TestQuery(testing.AppengineTestCase):
  app_module = main.app

  def test_query_headers(self):
    _clear_records()
    response = self.test_app.get('/query')
    self.assertEquals(response.headers['Access-Control-Allow-Origin'], '*')

  def test_query_empty(self):
    _clear_records()
    response = self.test_app.get('/query')
    self.assertEquals({
      'more': False,
      'results': [],
      'cursor': '',
    }, json.loads(response.body))

    Record(id='test_key', tags=['a', 'b', 'c'], fields={'test': 'field'}).put()
    response = self.test_app.get('/query')
    self.assertEquals({
      'more': False,
      'results': [{
        'key': 'test_key',
        'tags': ['a', 'b', 'c'],
        'fields': {'test': 'field'},
      }],
    }, _parse_body(response))

  def test_query_key(self):
    _clear_records()
    Record(id='match').put()
    Record(id='mismatch').put()
    response = self.test_app.get('/query', params={'key': 'match'})
    self.assertEquals({
      'more': False,
      'results': [{
        'key': 'match',
        'tags': [],
        'fields': {},
      }],
    }, _parse_body(response))

  def test_query_filtered_key(self):
    _clear_records()
    Record(id='match', tags=['match_tag']).put()
    response = self.test_app.get('/query',
        params={'key': 'match', 'tags': 'match_tag'})
    self.assertEquals({
      'more': False,
      'results': [{
        'key': 'match',
        'tags': ['match_tag'],
        'fields': {},
      }],
    }, _parse_body(response))

    Record(id='mismatched', tags=['mismatched_tag']).put()
    response = self.test_app.get('/query',
        params={'key': 'mismatched', 'tags': 'match_tag'})
    self.assertEquals({
      'more': False,
      'results': [],
    }, _parse_body(response))

  def test_query_count(self):
    _clear_records()
    for _ in range(10):
      Record().put()

    response = self.test_app.get('/query', params={'count': 1})
    self.assertEquals({
      'more': True,
      'results': [{'key': None, 'tags': [], 'fields': {}}],
    }, _parse_body(response))

    response = self.test_app.get('/query', params={'count': 10})
    self.assertEquals({
      'more': False,
      'results': [{'key': None, 'tags': [], 'fields': {}}] * 10,
    }, _parse_body(response))

    response = self.test_app.get('/query', params={'count': 100})
    self.assertEquals({
      'more': False,
      'results': [{'key': None, 'tags': [], 'fields': {}}] * 10,
    }, _parse_body(response))

  def test_query_cursor(self):
    _clear_records()
    for _ in range(10):
      Record().put()

    response = self.test_app.get('/query', params={'count': 4})
    packet = _parse_body(response, preserve_cursor=True)
    cursor = packet['cursor']
    self.assertEquals({
      'more': True,
      'cursor': cursor,
      'results': [{'key': None, 'tags': [], 'fields': {}}] * 4,
    }, packet)

    response = self.test_app.get('/query',
        params={'cursor': cursor, 'count': 4})
    packet = _parse_body(response, preserve_cursor=True)
    cursor = packet['cursor']
    self.assertEquals({
      'more': True,
      'cursor': cursor,
      'results': [{'key': None, 'tags': [], 'fields': {}}] * 4,
    }, packet)

    response = self.test_app.get('/query',
        params={'cursor': cursor, 'count': 4})
    packet = _parse_body(response, preserve_cursor=True)
    cursor = packet['cursor']
    self.assertEquals({
      'more': False,
      'cursor': cursor,
      'results': [{'key': None, 'tags': [], 'fields': {}}] * 2,
    }, packet)

  def test_query_begin(self):
    _clear_records()
    self.mock_now(datetime.utcfromtimestamp(10))
    Record(id='match').put()
    self.mock_now(datetime.utcfromtimestamp(0))
    Record(id='too_early').put()
    response = self.test_app.get('/query', params={'begin': 5})
    self.assertEquals({
      'more': False,
      'results': [{
        'key': 'match',
        'tags': [],
        'fields': {},
      }],
    }, _parse_body(response))

  def test_query_end(self):
    _clear_records()
    self.mock_now(datetime.utcfromtimestamp(0))
    Record(id='match').put()
    self.mock_now(datetime.utcfromtimestamp(10))
    Record(id='too_late').put()
    response = self.test_app.get('/query', params={'end': 5})
    self.assertEquals({
      'more': False,
      'results': [{
        'key': 'match',
        'tags': [],
        'fields': {},
      }],
    }, _parse_body(response))

  def test_query_tags(self):
    _clear_records()
    Record(id='match', tags=['match_tag_a', 'match_tag_b']).put()
    Record(id='match_extra',
        tags=['match_tag_a', 'match_tag_b', 'extra_tag']).put()
    Record(id='missing_tag', tags=['match_tag_a']).put()
    Record(id='wrong_tags', tags=['tag_mismatch_a', 'tag_mismatch_b']).put()
    Record(id='no_tags').put()
    response = self.test_app.get('/query',
        params={'tags': 'match_tag_a,match_tag_b'})
    self.assertEquals({
      'more': False,
      'results': [{
        'key': 'match',
        'tags': ['match_tag_a', 'match_tag_b'],
        'fields': {},
      }, {
        'key': 'match_extra',
        'tags': ['extra_tag', 'match_tag_a', 'match_tag_b'],
        'fields': {},
      }],
    }, _parse_body(response))

  def test_query_url_tags(self):
    _clear_records()
    Record(id='match', tags=['match_tag_a', 'match_tag_b', 'match_tag_c']).put()
    Record(id='match_extra',
        tags=['match_tag_a', 'match_tag_b', 'match_tag_c', 'extra_tag']).put()
    Record(id='missing_tag_a', tags=['match_tag_b', 'match_tag_c']).put()
    Record(id='missing_tag_c', tags=['match_tag_a', 'match_tag_b']).put()
    Record(id='wrong_tags', tags=['tag_mismatch_a', 'tag_mismatch_b']).put()
    Record(id='no_tags').put()
    response = self.test_app.get('/query/match_tag_a/match_tag_b',
        params={'tags': 'match_tag_b,match_tag_c'})
    self.assertEquals({
      'more': False,
      'results': [{
        'key': 'match',
        'tags': ['match_tag_a', 'match_tag_b', 'match_tag_c'],
        'fields': {},
      }, {
        'key': 'match_extra',
        'tags': ['extra_tag', 'match_tag_a', 'match_tag_b', 'match_tag_c'],
        'fields': {},
      }],
    }, _parse_body(response))

  def test_query_fields(self):
    _clear_records()
    Record(id='match', fields={
      'match_key_a': 'match_value_a',
      'match_key_b': 'match_value_b',
    }).put()
    Record(id='match_extra', fields={
      'match_key_a': 'match_value_a',
      'match_key_b': 'match_value_b',
      'extra_key': 'extra_value',
    }).put()
    Record(id='missing_key', fields={
      'match_key_a': 'match_value_a',
      'extra_key': 'extra_value',
    }).put()
    Record(id='wrong_value', fields={
      'match_key_a': 'match_value_a',
      'match_key_b': 'mismatched_value_b',
    }).put()
    Record(id='empty_fields').put()
    response = self.test_app.get('/query', params={
      'fields': json.dumps({
        'match_key_a': 'match_value_a',
        'match_key_b': 'match_value_b',
    })})
    self.assertEquals({
      'more': False,
      'results': [{
        'key': 'match',
        'tags': [],
        'fields': {
          'match_key_a': 'match_value_a',
          'match_key_b': 'match_value_b',
        },
      }, {
        'key': 'match_extra',
        'tags': [],
        'fields': {
          'match_key_a': 'match_value_a',
          'match_key_b': 'match_value_b',
          'extra_key': 'extra_value',
        },
      }],
    }, _parse_body(response))

  def test_query_full_keyless(self):
    _clear_records()
    self.mock_now(datetime.utcfromtimestamp(5))
    Record(id='match',
        tags=['match_tag_a', 'match_tag_b'],
        fields={
          'match_key_a': 'match_value_a',
          'match_key_b': 'match_value_b',
        },
    ).put()
    Record(id='match_extra',
        tags=['match_tag_a', 'match_tag_b', 'extra_tag'],
        fields={
          'match_key_a': 'match_value_a',
          'match_key_b': 'match_value_b',
          'extra_key': 'extra_value',
        },
    ).put()
    self.mock_now(datetime.utcfromtimestamp(0))
    Record(id='too_early',
        tags=['match_tag_a', 'match_tag_b'],
        fields={
          'match_key_a': 'match_value_a',
          'match_key_b': 'match_value_b',
        },
    ).put()
    self.mock_now(datetime.utcfromtimestamp(10))
    Record(id='too_late',
        tags=['match_tag_a', 'match_tag_b'],
        fields={
          'match_key_a': 'match_value_a',
          'match_key_b': 'match_value_b',
        },
    ).put()
    self.mock_now(datetime.utcfromtimestamp(5))
    Record(id='missing_tag',
        tags=['match_tag_a'],
        fields={
          'match_key_a': 'match_value_a',
          'match_key_b': 'match_value_b',
        },
    ).put()
    Record(id='empty_tags',
        fields={
          'match_key_a': 'match_value_a',
          'match_key_b': 'match_value_b',
        },
    ).put()
    Record(id='missing_field',
        tags=['match_tag_a', 'match_tag_b'],
        fields={
          'match_key_a': 'match_value_a',
        },
    ).put()
    Record(id='wrong_field',
        tags=['match_tag_a', 'match_tag_b'],
        fields={
          'match_key_a': 'match_value_a',
          'match_key_b': 'mismatched_value_b',
        },
    ).put()
    Record(id='empty_fields',
        tags=['match_tag_a', 'match_tag_b'],
    ).put()
    response = self.test_app.get('/query', params={
      'begin': 4,
      'end': 6,
      'tags': 'match_tag_a,match_tag_b',
      'fields': json.dumps({
        'match_key_a': 'match_value_a',
        'match_key_b': 'match_value_b',
      },
    )})
    self.maxDiff = None
    self.assertEquals({
      'more': False,
      'results': [{
        'key': 'match',
        'tags': ['match_tag_a', 'match_tag_b'],
        'fields': {
          'match_key_a': 'match_value_a',
          'match_key_b': 'match_value_b',
        },
      }, {
        'key': 'match_extra',
        'tags': ['extra_tag', 'match_tag_a', 'match_tag_b'],
        'fields': {
          'match_key_a': 'match_value_a',
          'match_key_b': 'match_value_b',
          'extra_key': 'extra_value',
        },
      }],
    }, _parse_body(response))


def _clear_records(): # pragma: no cover
  for record in Record.query():
    record.key.delete()
  assert Record.query().count() == 0

def _parse_body(response,
    preserve_cursor=False, preserve_timestamp=False): # pragma: no cover
  packet = json.loads(response.body)
  if not preserve_cursor:
    del packet['cursor']
  packet['results'].sort()
  for result in packet['results']:
    result['tags'].sort()
    if not preserve_timestamp:
      del result['timestamp']
  return packet
