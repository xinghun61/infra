# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

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
          },
          'bar': {
            'connected_slaves': 5,
            'current_builds': 6,
            'pending_builds': 7,
            'state': "idle",
            'total_slaves': 8,
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


class ClockPollerTest(unittest.TestCase):
  def test_response(self):
    p = pollers.ClockPoller('', {'x': 'y'})

    p.handle_response({'server_uptime': 123})
    self.assertEqual(123, p.uptime.get({'x': 'y'}))


class BuildStatePollerTest(unittest.TestCase):
  def test_response(self):
    p = pollers.BuildStatePoller('', {'x': 'y'})

    p.handle_response({
      'accepting_builds': True,
      'builders': [
        {
          'builderName': 'foo',
          'currentBuilds': [],
          'pendingBuilds': 4,
          'state': 'offline',
        },
        {
          'builderName': 'bar',
          'currentBuilds': [1, 2, 3],
          'pendingBuilds': 0,
          'state': 'building',
        },
      ]
    })
    self.assertEqual(True, p.accepting_builds.get({'x': 'y'}))
    self.assertEqual(0, p.current_builds.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual(4, p.pending_builds.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual('offline', p.state.get({'builder': 'foo', 'x': 'y'}))
    self.assertEqual(3, p.current_builds.get({'builder': 'bar', 'x': 'y'}))
    self.assertEqual(0, p.pending_builds.get({'builder': 'bar', 'x': 'y'}))
    self.assertEqual('building', p.state.get({'builder': 'bar', 'x': 'y'}))


class SlavesPollerTest(unittest.TestCase):
  def test_response(self):
    p = pollers.SlavesPoller('', {})

    p.handle_response({
      'slave1': {
        'builders': {},
        'connected': True,
        'runningBuilds': [],
      },
      'slave2': {
        'builders': {
          'builder1': {},
          'builder2': {},
        },
        'connected': True,
        'runningBuilds': [1, 2],
      },
      'slave3': {
        'builders': {
          'builder1': {},
        },
        'connected': False,
        'runningBuilds': [],
      },
    })
    self.assertEqual(2, p.total.get({'builder': 'builder1'}))
    self.assertEqual(1, p.total.get({'builder': 'builder2'}))
    self.assertEqual(1, p.connected.get({'builder': 'builder1'}))
    self.assertEqual(1, p.connected.get({'builder': 'builder2'}))
    self.assertEqual(1, p.running_builds.get({'builder': 'builder1'}))
    self.assertEqual(1, p.running_builds.get({'builder': 'builder2'}))
