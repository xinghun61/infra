# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import datetime
import os
import time
import unittest

import gae_ts_mon
import mock
import webapp2

from infra_libs.ts_mon import config
from infra_libs.ts_mon.common import http_metrics
from infra_libs.ts_mon.common import interface
from infra_libs.ts_mon.common import monitors
from infra_libs.ts_mon.common import targets
from infra_libs.ts_mon.common.test import stubs
from testing_utils import testing


class InitializeTest(testing.AppengineTestCase):
  def setUp(self):
    super(InitializeTest, self).setUp()

    config.reset_for_unittest()
    target = targets.TaskTarget('test_service', 'test_job',
                                'test_region', 'test_host')
    self.mock_state = interface.State(target=target)
    self.mock_state.metrics = copy.copy(interface.state.metrics)
    mock.patch('infra_libs.ts_mon.common.interface.state',
        new=self.mock_state).start()

    mock.patch('infra_libs.ts_mon.common.monitors.PubSubMonitor',
               autospec=True).start()

  def tearDown(self):
    config.reset_for_unittest()
    self.assertEqual([], list(config.flush_callbacks))
    mock.patch.stopall()
    super(InitializeTest, self).tearDown()

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

  def test_instruments_app(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.write('success!')

    app = webapp2.WSGIApplication([('/', Handler)])
    config.initialize(app, is_local_unittest=False)

    app.get_response('/')

    self.assertEqual(1, http_metrics.server_response_status.get({
        'name': '^/$', 'status': 200, 'is_robot': False}))

  def test_instruments_app_only_once(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.write('success!')

    app = webapp2.WSGIApplication([('/', Handler)])
    config.initialize(app, is_local_unittest=False)
    config.initialize(app, is_local_unittest=False)
    config.initialize(app, is_local_unittest=False)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 200, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_unregister_global_metrics_callback(self):
    config.register_global_metrics_callback('test', 'callback')
    self.assertEqual(['test'], list(config.flush_callbacks))
    config.register_global_metrics_callback('nonexistent', None)
    self.assertEqual(['test'], list(config.flush_callbacks))
    config.register_global_metrics_callback('test', None)
    self.assertEqual([], list(config.flush_callbacks))

  def test_reset_cumulative_metrics(self):
    gauge = gae_ts_mon.GaugeMetric('gauge')
    counter = gae_ts_mon.CounterMetric('counter')
    gauge.set(5)
    counter.increment()
    self.assertEqual(5, gauge.get())
    self.assertEqual(1, counter.get())

    config._reset_cumulative_metrics()
    self.assertEqual(5, gauge.get())
    self.assertIsNone(counter.get())

  def test_flush_metrics_no_task_num(self):
    # We are not assigned task_num yet; cannot send metrics.
    time_now = datetime.datetime(2016, 2, 8, 1, 0)
    more_than_min_ago = time_now - datetime.timedelta(seconds=61)
    interface.state.last_flushed = more_than_min_ago
    entity = config._get_instance_entity()
    entity.task_num = -1
    interface.state.target.task_num = -1
    self.assertFalse(config.flush_metrics_if_needed(time_fn=lambda: time_now))

  def test_flush_metrics_no_task_num_too_long(self):
    # We are not assigned task_num for too long; cannot send metrics.
    time_now = datetime.datetime(2016, 2, 8, 1, 0)
    too_long_ago = time_now - datetime.timedelta(
        seconds=config.INSTANCE_EXPECTED_TO_HAVE_TASK_NUM_SEC+1)
    interface.state.last_flushed = too_long_ago
    entity = config._get_instance_entity()
    entity.task_num = -1
    entity.last_updated = too_long_ago
    interface.state.target.task_num = -1
    self.assertFalse(config.flush_metrics_if_needed(time_fn=lambda: time_now))

  def test_flush_metrics_purged(self):
    # We lost our task_num; cannot send metrics.
    time_now = datetime.datetime(2016, 2, 8, 1, 0)
    more_than_min_ago = time_now - datetime.timedelta(seconds=61)
    interface.state.last_flushed = more_than_min_ago
    entity = config._get_instance_entity()
    entity.task_num = -1
    interface.state.target.task_num = 2
    self.assertFalse(config.flush_metrics_if_needed(time_fn=lambda: time_now))

  def test_flush_metrics_too_early(self):
    # Too early to send metrics.
    time_now = datetime.datetime(2016, 2, 8, 1, 0)
    less_than_min_ago = time_now - datetime.timedelta(seconds=59)
    interface.state.last_flushed = less_than_min_ago
    entity = config._get_instance_entity()
    entity.task_num = 2
    self.assertFalse(config.flush_metrics_if_needed(time_fn=lambda: time_now))

  @mock.patch('infra_libs.ts_mon.common.interface.flush', autospec=True)
  def test_flush_metrics_successfully(self, mock_flush):
    # We have task_num and due for sending metrics.
    time_now = datetime.datetime(2016, 2, 8, 1, 0)
    more_than_min_ago = time_now - datetime.timedelta(seconds=61)
    interface.state.last_flushed = more_than_min_ago
    entity = config._get_instance_entity()
    entity.task_num = 2
    # Global metrics must be erased after flush.
    test_global_metric = gae_ts_mon.GaugeMetric('test')
    test_global_metric.set(42)
    config.register_global_metrics([test_global_metric])
    self.assertEqual(42, test_global_metric.get())
    self.assertTrue(config.flush_metrics_if_needed(time_fn=lambda: time_now))
    self.assertEqual(None, test_global_metric.get())
    mock_flush.assert_called_once_with()

  @mock.patch('gae_ts_mon.config.flush_metrics_if_needed', autospec=True,
              return_value=True)
  def test_shutdown_hook_flushed(self, _mock_flush):
    id = config._get_instance_entity().key.id()
    with config.instance_namespace_context():
      self.assertIsNotNone(config.Instance.get_by_id(id))
    config._shutdown_hook()
    with config.instance_namespace_context():
      self.assertIsNone(config.Instance.get_by_id(id))

  @mock.patch('gae_ts_mon.config.flush_metrics_if_needed', autospec=True,
              return_value=False)
  def test_shutdown_hook_not_flushed(self, _mock_flush):
    id = config._get_instance_entity().key.id()
    with config.instance_namespace_context():
      self.assertIsNotNone(config.Instance.get_by_id(id))
    config._shutdown_hook()
    with config.instance_namespace_context():
      self.assertIsNone(config.Instance.get_by_id(id))

  def test_internal_callback(self):
    # Smoke test.
    config._internal_callback()


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

    fields = {'name': '^/$', 'status': 200, 'is_robot': False}
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

    fields = {'name': '^/$', 'status': 417, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_set_status(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        self.response.set_status(418)

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 418, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_exception(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        raise ValueError

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 500, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_http_exception(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        raise webapp2.exc.HTTPExpectationFailed()

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 417, 'is_robot': False}
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

    fields = {'name': '^/$', 'status': 418, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_robot(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        ret = webapp2.Response()
        ret.set_status(200)
        return ret

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/', user_agent='GoogleBot')

    fields = {'name': '^/$', 'status': 200, 'is_robot': True}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_missing_response_content_length(self):
    class Handler(webapp2.RequestHandler):
      def get(self):
        del self.response.headers['content-length']

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/')

    fields = {'name': '^/$', 'status': 200, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertIsNone(http_metrics.server_response_bytes.get(fields))

  def test_not_found(self):
    app = webapp2.WSGIApplication([])
    config.instrument_wsgi_application(app)

    app.get_response('/notfound')

    fields = {'name': '', 'status': 404, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))

  def test_post(self):
    class Handler(webapp2.RequestHandler):
      def post(self):
        pass

    app = webapp2.WSGIApplication([('/', Handler)])
    config.instrument_wsgi_application(app)

    app.get_response('/', POST='foo')

    fields = {'name': '^/$', 'status': 200, 'is_robot': False}
    self.assertEqual(1, http_metrics.server_response_status.get(fields))
    self.assertEqual(
        len('foo'), http_metrics.server_request_bytes.get(fields).sum)
