# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import tempfile
import unittest

import mock
import requests

from infra.services.mastermon import pollers


class FakePoller(pollers.Poller):
  endpoint = '/foo'

  def __init__(self, base_url):
    super(FakePoller, self).__init__(base_url, {})
    self.called_with_data = None

  def handle_response(self, data):
    self.called_with_data = data


@mock.patch('requests.get')
class PollerTest(unittest.TestCase):
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


class VarzPollerTest(unittest.TestCase):
  def test_response(self):
    p = pollers.VarzPoller('', {'x': 'y'})

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
            'recent_builds_by_status': {
              '0': 1,
              '2': 2,
              '4': 3,
              'building': 4,
            },
            'recent_finished_build_times': [1, 2, 3],
            'recent_successful_build_times': [1, 2, 3],
          },
          'bar': {
            'connected_slaves': 5,
            'current_builds': 6,
            'pending_builds': 7,
            'state': "idle",
            'total_slaves': 8,
            'recent_builds_by_status': {
              '0': 1,
              '2': 2,
              '4': 3,
              'building': 4,
            },
            'recent_finished_build_times': [1, 2, 3],
            'recent_successful_build_times': [1, 2, 3],
          },
        },
    })

    self.assertEqual(123, p.uptime.get({'x': 'y'}))
    self.assertEqual(True, p.accepting_builds.get({'x': 'y'}))
    self.assertEqual(1, p.connected.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual(2, p.current_builds.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual(3, p.pending_builds.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual(4, p.total.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual('offline', p.state.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual(5, p.connected.get({'builder': 'bar', 'x': 'y'}))
    self.assertEqual(6, p.current_builds.get({'builder': 'bar', 'x': 'y'}))
    self.assertEqual(7, p.pending_builds.get({'builder': 'bar', 'x': 'y'}))
    self.assertEqual(8, p.total.get({'builder': 'bar', 'x': 'y'}))
    self.assertEqual('idle', p.state.get({'builder': 'bar', 'x': 'y'}))

    self.assertEqual(1, p.recent_builds.get(
        {'builder': 'foo', 'x': 'y', 'status': 'success'}))
    self.assertEqual(4, p.recent_builds.get(
        {'builder': 'foo', 'x': 'y', 'status': 'building'}))

    self.assertIsNotNone(p.recent_finished_build_times.get(
        {'builder': 'foo', 'x': 'y'}))
    self.assertIsNotNone(p.recent_successful_build_times.get(
        {'builder': 'foo', 'x': 'y'}))

  def test_response_with_missing_data(self):
    p = pollers.VarzPoller('', {'x': 'y'})

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

    self.assertEqual(123, p.uptime.get({'x': 'y'}))
    self.assertEqual(True, p.accepting_builds.get({'x': 'y'}))
    self.assertEqual(0, p.connected.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual(0, p.current_builds.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual(0, p.pending_builds.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual(4, p.total.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual('offline', p.state.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual(5, p.connected.get({'builder': 'bar', 'x': 'y'}))
    self.assertEqual(6, p.current_builds.get({'builder': 'bar', 'x': 'y'}))
    self.assertEqual(7, p.pending_builds.get({'builder': 'bar', 'x': 'y'}))
    self.assertEqual(0, p.total.get({'builder': 'bar', 'x': 'y'}))
    self.assertEqual('unknown', p.state.get({'builder': 'bar', 'x': 'y'}))


class FilePollerTest(unittest.TestCase):
  @staticmethod
  def create_data_file(data_list):
    with tempfile.NamedTemporaryFile(delete=False) as f:
      for data in data_list:
        f.write('%s\n' % json.dumps(data))
      return f.name
    # FIXME(pgervais): We have to close the file on windows to be able
    # to open it a second time.
    # https://docs.python.org/2/library/tempfile.html#tempfile.NamedTemporaryFile

  def test_no_file(self):
    p = pollers.FilePoller('no-such-file', {})
    self.assertTrue(p.poll())

  @mock.patch('infra_libs.ts_mon.CounterMetric.increment')
  def test_file_has_data(self, fake_increment):
    result1 = {'builder': 'b1', 'slave': 's1', 'result': 'r1'}
    result2 = {'builder': 'b1', 'slave': 's1', 'result': 'r1'}
    data1 = result1.copy()
    data1['random'] = 'value'
    filename = self.create_data_file([data1, result2])
    p = pollers.FilePoller(filename, {})
    self.assertTrue(p.poll())
    fake_increment.assert_any_call(result1)
    fake_increment.assert_any_call(result2)
    with self.assertRaises(OSError):
      os.remove(filename)

  def test_file_has_bad_data(self):
    filename = self.create_data_file([])
    with open(filename, 'a') as f:
      f.write('}')
    p = pollers.FilePoller(filename, {})
    self.assertTrue(p.poll())
    with self.assertRaises(OSError):
      os.remove(filename)

  def test_safe_remove_error(self):
    """Smoke test: the function should not raise an exception."""
    pollers.safe_remove('nonexistent-file')
