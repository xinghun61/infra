# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import time
import unittest

import mock
import requests

from infra_libs import temporary_directory
from infra_libs import ts_mon
from infra.services.mastermon import pollers


class FakePoller(pollers.Poller):
  endpoint = '/foo'

  def __init__(self, base_url, **kwargs):
    super(FakePoller, self).__init__(base_url, {'master': 'foo'}, **kwargs)
    self.called_with_data = None

  def handle_response(self, data):
    self.called_with_data = data


@mock.patch('requests.get')
class PollerTest(unittest.TestCase):
  def setUp(self):
    super(PollerTest, self).setUp()

    ts_mon.reset_for_unittest()

  def test_requests_url(self, mock_get):
    response = mock_get.return_value
    response.json.return_value = {'foo': 'bar'}
    response.status_code = 200

    p = FakePoller('http://foobar')
    self.assertTrue(p.poll())

    self.assertEquals(1, mock_get.call_count)
    self.assertEquals('http://foobar/json/foo', mock_get.call_args[0][0])

  def test_strips_trailing_slashes(self, mock_get):
    response = mock_get.return_value
    response.json.return_value = {'foo': 'bar'}
    response.status_code = 200

    p = FakePoller('http://foobar////')
    self.assertTrue(p.poll())

    self.assertEquals(1, mock_get.call_count)
    self.assertEquals('http://foobar/json/foo', mock_get.call_args[0][0])

  def test_returns_false_for_non_200(self, mock_get):
    response = mock_get.return_value
    response.status_code = 404

    p = FakePoller('http://foobar')
    self.assertFalse(p.poll())

  def test_returns_false_for_exception(self, mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError

    p = FakePoller('http://foobar')
    self.assertFalse(p.poll())

  def test_calls_handle_response(self, mock_get):
    response = mock_get.return_value
    response.json.return_value = {'foo': 'bar'}
    response.status_code = 200

    p = FakePoller('http://foobar')
    self.assertTrue(p.poll())
    self.assertEqual({'foo': 'bar'}, p.called_with_data)

  def test_handles_invalid_json(self, mock_get):
    response = mock_get.return_value
    response.json.side_effect = ValueError
    response.status_code = 200

    p = FakePoller('http://foobar')
    self.assertFalse(p.poll())
    self.assertIsNone(p.called_with_data)

  def test_durations_metric(self, mock_get):
    response = mock_get.return_value
    response.json.return_value = {'foo': 'bar'}
    response.status_code = 200

    mock_time = mock.create_autospec(time.time, spec_set=True)
    mock_time.side_effect = [123.0, 124.2]

    p = FakePoller('http://foobar', time_fn=mock_time)
    self.assertTrue(p.poll())

    dist = pollers.Poller.durations.get(
        {'master': 'foo', 'poller': 'FakePoller'})
    self.assertEquals(1, dist.count)
    self.assertAlmostEquals(1200, dist.sum)


class VarzPollerTest(unittest.TestCase):
  def setUp(self):
    super(VarzPollerTest, self).setUp()

    ts_mon.reset_for_unittest()

  def test_response(self):
    p = pollers.VarzPoller('', {'master': 'a'})

    p.handle_response({
        'server_uptime': 123,
        'accepting_builds': True,
        'builders': {
          'foo': {
            'connected_slaves': 1,
            'current_builds': 2,
            'pending_builds': 3,
            'state': "offline",
            'total_slaves': 4,
            'recent_finished_build_times': [1, 2, 3],
            'recent_successful_build_times': [1, 2, 3],
          },
          'bar': {
            'connected_slaves': 5,
            'current_builds': 6,
            'pending_builds': 7,
            'state': "idle",
            'total_slaves': 8,
          },
        },
        'db_thread_pool': {
          'queue': 9,
          'waiting': 10,
          'working': 11,
        },
    })

    self.assertEqual(123, p.uptime.get({'master': 'a'}))
    self.assertEqual(True, p.accepting_builds.get({'master': 'a'}))
    self.assertEqual(1, p.connected.get({'builder': 'foo', 'master': 'a'}))
    self.assertEqual(2, p.current_builds.get({'builder': 'foo', 'master': 'a'}))
    self.assertEqual(3, p.pending_builds.get({'builder': 'foo', 'master': 'a'}))
    self.assertEqual(4, p.total.get({'builder': 'foo', 'master': 'a'}))
    self.assertEqual('offline', p.state.get({'builder': 'foo', 'master': 'a'}))
    self.assertEqual(5, p.connected.get({'builder': 'bar', 'master': 'a'}))
    self.assertEqual(6, p.current_builds.get({'builder': 'bar', 'master': 'a'}))
    self.assertEqual(7, p.pending_builds.get({'builder': 'bar', 'master': 'a'}))
    self.assertEqual(8, p.total.get({'builder': 'bar', 'master': 'a'}))
    self.assertEqual('idle', p.state.get({'builder': 'bar', 'master': 'a'}))
    self.assertEqual(9, p.pool_queue.get({'master': 'a'}))
    self.assertEqual(10, p.pool_waiting.get({'master': 'a'}))
    self.assertEqual(11, p.pool_working.get({'master': 'a'}))

  def test_response_with_missing_data(self):
    p = pollers.VarzPoller('', {'master': 'a'})

    p.handle_response({
        'server_uptime': 123,
        'accepting_builds': True,
        'builders': {
          'foo': {
            'state': "offline",
            'total_slaves': 4,
          },
          'bar': {
            'connected_slaves': 5,
            'current_builds': 6,
            'pending_builds': 7,
          },
        },
    })

    self.assertEqual(123, p.uptime.get({'master': 'a'}))
    self.assertEqual(True, p.accepting_builds.get({'master': 'a'}))
    self.assertEqual(0, p.connected.get({'builder': 'foo', 'master': 'a'}))
    self.assertEqual(0, p.current_builds.get({'builder': 'foo', 'master': 'a'}))
    self.assertEqual(0, p.pending_builds.get({'builder': 'foo', 'master': 'a'}))
    self.assertEqual(4, p.total.get({'builder': 'foo', 'master': 'a'}))
    self.assertEqual('offline', p.state.get({'builder': 'foo', 'master': 'a'}))
    self.assertEqual(5, p.connected.get({'builder': 'bar', 'master': 'a'}))
    self.assertEqual(6, p.current_builds.get({'builder': 'bar', 'master': 'a'}))
    self.assertEqual(7, p.pending_builds.get({'builder': 'bar', 'master': 'a'}))
    self.assertEqual(0, p.total.get({'builder': 'bar', 'master': 'a'}))
    self.assertEqual('unknown', p.state.get({'builder': 'bar', 'master': 'a'}))
    self.assertIsNone(p.pool_queue.get({'master': 'a'}))
    self.assertIsNone(p.pool_waiting.get({'master': 'a'}))
    self.assertIsNone(p.pool_working.get({'master': 'a'}))


class FilePollerTest(unittest.TestCase):
  @staticmethod
  def create_data_file(dirname, data_list):
    with open(os.path.join(dirname, 'ts_mon.log'), 'w') as f:
      for data in data_list:
        f.write('%s\n' % json.dumps(data))
      return f.name

  def test_no_file(self):
    with temporary_directory(prefix='poller-test-') as tempdir:
      filename = os.path.join(tempdir, 'no-such-file')
      p = pollers.FilePoller(filename, {'master': 'foo'})
      self.assertTrue(p.poll())
      self.assertFalse(os.path.isfile(pollers.rotated_filename(filename)))

  def test_file_has_data(self):
    result1 = {'builder': 'b1', 'slave': 's1',
               'result': 'r1', 'project_id': 'chromium',
               'subproject_tag': 'unknown'}
    result2 = {'builder': 'b1', 'slave': 's1',
               'result': 'r1', 'project_id': 'unknown',
               'subproject_tag': 'unknown'}
    # Keep it for branch coverage.
    result3 = {'builder': 'b1', 'slave': 's1',
               'step_result': 'r1', 'project_id': 'chromium',
               'subproject_tag': 'unknown'}
    # Check that we've listed all the required metric fields.
    self.assertEqual(set(result1),
                     set(x.name for x in pollers.FilePoller.fields_from_json))
    self.assertEqual(set(result2),
                     set(x.name for x in pollers.FilePoller.fields_from_json))

    data = [r.copy() for r in (result1, result2, result3)]
    data[0]['random'] = 'value'  # Extra field, should be ignored.
    del data[1]['project_id']    # Missing field, should become 'unknown'.
    data[1]['duration_s'] = 5
    data[1]['pending_s'] = 1
    data[1]['total_s'] = data[1]['pending_s'] + data[1]['duration_s']
    data[1]['pre_test_time_s'] = 2
    with temporary_directory(prefix='poller-test-') as tempdir:
      filename = self.create_data_file(tempdir, data)
      p = pollers.FilePoller(filename, {'master': 'foo'})
      self.assertTrue(p.poll())

      fields = {'master': 'foo'}
      fields.update(result1)
      self.assertEqual(pollers.FilePoller.result_count.get(fields), 1)
      fields = {'master': 'foo'}
      fields.update(result2)
      self.assertEqual(pollers.FilePoller.result_count.get(fields), 1)

      self.assertFalse(os.path.isfile(filename))
      # Make sure the rotated file is still there - for debugging.
      self.assertTrue(os.path.isfile(pollers.rotated_filename(filename)))

  def test_file_has_bad_data(self):
    """Mostly a smoke test: don't crash on bad data."""
    with temporary_directory(prefix='poller-test-') as tempdir:
      filename = self.create_data_file(tempdir, [])
      with open(filename, 'a') as f:
        f.write('}')
      p = pollers.FilePoller(filename, {'master': 'foo'})
      self.assertTrue(p.poll())
      self.assertFalse(os.path.isfile(filename))
      # Make sure the rotated file is still there - for debugging.
      self.assertTrue(os.path.isfile(pollers.rotated_filename(filename)))

  def test_safe_remove_error(self):
    """Smoke test: the function should not raise an exception."""
    pollers.safe_remove('nonexistent-file')
