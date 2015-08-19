# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

from infra_libs.ts_mon.common import http_metrics
from infra_libs import instrumented_requests

import requests
import mock


class InstrumentedRequestsTest(unittest.TestCase):
  def setUp(self):
    super(InstrumentedRequestsTest, self).setUp()
    http_metrics._reset_for_testing()

    self.response = requests.Response()
    self.response.elapsed = datetime.timedelta(seconds=2, milliseconds=500)
    self.response.status_code = 200
    self.response.request = requests.PreparedRequest()
    self.response.request.prepare_headers(None)

    self.hook = instrumented_requests.instrumentation_hook('foo')

  def tearDown(self):
    super(InstrumentedRequestsTest, self).tearDown()
    mock.patch.stopall()

  def test_success_status(self):
    self.hook(self.response)

    self.assertEquals(1, http_metrics.response_status.get(
        {'name': 'foo', 'client': 'requests', 'status': 200}))
    self.assertEquals(0, http_metrics.response_status.get(
        {'name': 'foo', 'client': 'requests', 'status': 404}))

  def test_error_status(self):
    self.response.status_code = 404
    self.hook(self.response)

    self.assertEquals(0, http_metrics.response_status.get(
        {'name': 'foo', 'client': 'requests', 'status': 200}))
    self.assertEquals(1, http_metrics.response_status.get(
        {'name': 'foo', 'client': 'requests', 'status': 404}))

  def test_response_bytes_none(self):
    self.hook(self.response)

    self.assertEquals(0, http_metrics.response_bytes.get(
        {'name': 'foo', 'client': 'requests'}).sum)

  def test_response_bytes(self):
    self.response.headers['content-length'] = '7'
    self.hook(self.response)

    self.assertEquals(7, http_metrics.response_bytes.get(
        {'name': 'foo', 'client': 'requests'}).sum)

  def test_request_bytes_none(self):
    self.hook(self.response)

    self.assertEquals(0, http_metrics.request_bytes.get(
        {'name': 'foo', 'client': 'requests'}).sum)

  def test_request_bytes(self):
    self.response.request.headers['content-length'] = '5'
    self.hook(self.response)

    self.assertEquals(5, http_metrics.request_bytes.get(
        {'name': 'foo', 'client': 'requests'}).sum)

  def test_durations(self):
    self.hook(self.response)

    self.assertEquals(2500, http_metrics.durations.get(
        {'name': 'foo', 'client': 'requests'}).sum)

  def test_wrap(self):
    requests._instrumented_test = mock.Mock()
    f = requests._instrumented_test
    instrumented_requests._wrap(
        '_instrumented_test', 'foo', 'http://example.com')

    self.assertTrue(f.called)
    self.assertEquals(('http://example.com',), f.call_args[0])
    self.assertIn('hooks', f.call_args[1])
    self.assertIn('response', f.call_args[1]['hooks'])
    self.assertTrue(hasattr(f.call_args[1]['hooks']['response'], '__call__'))

  def test_wrap_merges_hooks(self):
    requests._instrumented_test = mock.Mock()
    f = requests._instrumented_test
    instrumented_requests._wrap(
        '_instrumented_test', 'foo', 'http://example.com',
        hooks={'foo': lambda: 42})

    self.assertTrue(f.called)
    self.assertEquals(('http://example.com',), f.call_args[0])
    self.assertIn('hooks', f.call_args[1])
    self.assertIn('response', f.call_args[1]['hooks'])
    self.assertIn('foo', f.call_args[1]['hooks'])
    self.assertTrue(hasattr(f.call_args[1]['hooks']['response'], '__call__'))
    self.assertEquals(42, f.call_args[1]['hooks']['foo']())
