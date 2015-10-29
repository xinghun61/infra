# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time
import unittest

import gae_ts_mon
import mock
import webapp2

from infra_libs.ts_mon import config
from infra_libs.ts_mon import memcache_metric_store
from infra_libs.ts_mon.common import http_metrics
from infra_libs.ts_mon.common import interface
from infra_libs.ts_mon.common import monitors
from infra_libs.ts_mon.common.test import stubs
from testing_utils import testing


class InitializeTest(testing.AppengineTestCase):
  def setUp(self):
    super(InitializeTest, self).setUp()

    self.mock_state = stubs.MockState()
    mock.patch('infra_libs.ts_mon.common.interface.state',
        new=self.mock_state).start()

    mock.patch('infra_libs.ts_mon.common.monitors.PubSubMonitor',
               autospec=True).start()

  def tearDown(self):
    super(InitializeTest, self).tearDown()

    mock.patch.stopall()

  def test_sets_target(self):
    config.initialize(is_local_unittest=False)

    self.assertEqual('testbed-test', self.mock_state.target.service_name)
    self.assertEqual('default', self.mock_state.target.job_name)
    self.assertEqual('appengine', self.mock_state.target.region)
    self.assertEqual('testbed', self.mock_state.target.hostname)

  def test_sets_monitor(self):
    os.environ['SERVER_SOFTWARE'] = 'Production'  # != 'Development'

    config.initialize(is_local_unittest=False)

    self.assertEquals(1, monitors.PubSubMonitor.call_count)

  def test_sets_monitor_dev(self):
    config.initialize(is_local_unittest=False)

    self.assertFalse(monitors.PubSubMonitor.called)
    self.assertIsInstance(self.mock_state.global_monitor, monitors.DebugMonitor)

  def test_already_configured(self):
    self.mock_state.global_monitor = monitors.DebugMonitor()
    self.mock_state.store = memcache_metric_store.MemcacheMetricStore(
        self.mock_state)

    config.initialize(is_local_unittest=False)

    self.assertIsNone(self.mock_state.target)

  def test_instruments_app(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.write('success!')

    app = webapp2.WSGIApplication([('/', Handler)])
    config.initialize(app, is_local_unittest=False)

    app.get_response('/')

    self.assertEqual(1, http_metrics.server_response_status.get({
        'name': '^/$', 'status': 200}))

  def test_instruments_app_only_once(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.write('success!')

    app = webapp2.WSGIApplication([('/', Handler)])
    config.initialize(app, is_local_unittest=False)
    config.initialize(app, is_local_unittest=False)
    config.initialize(app, is_local_unittest=False)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 200}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))


class InstrumentTest(testing.AppengineTestCase):
  def setUp(self):
    super(InstrumentTest, self).setUp()

    interface.reset_for_unittest()

    self.next_time = 42.0
    self.time_increment = 3.0

  def fake_time(self):
    ret = self.next_time
    self.next_time += self.time_increment
    return ret

  def test_success(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.write('success!')

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app, time_fn=self.fake_time)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 200}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertEqual(3000, http_metrics.server_durations.get(fields).sum)
    self.assertEqual(
        len('success!'), http_metrics.server_response_bytes.get(fields).sum)

  def test_abort(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.abort(417)

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 417}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_set_status(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.set_status(418)

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 418}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_exception(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        raise ValueError

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 500}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_http_exception(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        raise webapp2.exc.HTTPExpectationFailed()

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 417}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_return_response(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        ret = webapp2.Response()
        ret.set_status(418)
        return ret

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 418}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_missing_response_content_length(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        del self.response.headers['content-length']

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 200}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertIsNone(http_metrics.server_response_bytes.get(fields))

  def test_not_found(self):
    app = webapp2.WSGIApplication([])
    config.instrument_wsgi_application(app)

    app.get_response('/notfound')

    fields = {'name': '', 'status': 404}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_post(self):
    class Handler(webapp2.RequestHandler):
      def post(self):
        pass

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/', POST='foo')

    fields = {'name': '^/$', 'status': 200}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertEqual(
        len('foo'), http_metrics.server_request_bytes.get(fields).sum)
