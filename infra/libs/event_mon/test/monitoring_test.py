# -*- encoding:utf-8 -*-
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from infra.libs import event_mon
from infra.libs.event_mon import config, router
from infra.libs.event_mon import monitoring
from infra.libs.event_mon.chrome_infra_log_pb2 import ChromeInfraEvent
from infra.libs.event_mon.chrome_infra_log_pb2 import ServiceEvent
from infra.libs.event_mon.log_request_lite_pb2 import LogRequestLite


class MonitoringTest(unittest.TestCase):

  # We have to setup and tear down event_mon for each test to avoid
  # interactions between tests because event_mon stores a global state.
  def setUp(self):
    event_mon.setup_monitoring(run_type='dry')

  def tearDown(self):
    event_mon.close()

  def test_constants(self):
    # Make sure constants have not been renamed since they're part of the API.
    self.assertTrue(event_mon.EVENT_TYPES)
    self.assertTrue(event_mon.TIMESTAMP_KINDS)

  def test_get_service_event_default(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    log_event = monitoring._get_service_event('START')
    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)
    self.assertTrue(log_event.HasField('event_time_ms'))
    self.assertTrue(log_event.HasField('source_extension'))

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('service_event'))
    self.assertTrue(event.service_event.HasField('type'))
    self.assertEquals(event.service_event.type, ServiceEvent.START)

  def test_get_service_event_correct_versions(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    code_version = [
      {'source_url': 'https://fake.url/thing',
       'revision': '708329c2aeece8aac33af6a5a772ffb14b55903f'},
      {'source_url': 'svn://fake_svn.url/other_thing',
       'revision': '123456'},
      {'source_url': 'https://other_fake.url/yet_another_thing',
       'version': 'v2.0'},
      {'source_url': 'https://other_fake2.url/yet_another_thing2',
       'dirty': True},
      ]

    log_event = monitoring._get_service_event('START',
                                              code_version=code_version)
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    code_version_p = event.service_event.code_version
    self.assertEquals(len(code_version_p), len(code_version))

    self.assertEqual(code_version_p[0].source_url,
                     code_version[0]['source_url'])
    self.assertEqual(code_version_p[0].git_hash, code_version[0]['revision'])
    self.assertFalse(code_version_p[0].HasField('svn_revision'))

    self.assertEqual(code_version_p[1].source_url,
                     code_version[1]['source_url'])
    self.assertEqual(code_version_p[1].svn_revision,
                     int(code_version[1]['revision']))
    self.assertFalse(code_version_p[1].HasField('git_hash'))

    self.assertEqual(code_version_p[2].source_url,
                     code_version[2]['source_url'])
    self.assertFalse(code_version_p[2].HasField('svn_revision'))
    self.assertEqual(code_version_p[2].version,
                     code_version[2]['version'])

    self.assertEqual(code_version_p[3].source_url,
                     code_version[3]['source_url'])
    self.assertEqual(code_version_p[3].dirty, True)

  def test_get_service_event_crash_simple(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    log_event = monitoring._get_service_event('CRASH')
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertEqual(event.service_event.type, ServiceEvent.CRASH)

  def test_get_service_event_crash_with_ascii_trace(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    stack_trace = 'A nice ascii string'
    log_event = monitoring._get_service_event('CRASH',
                                              stack_trace=stack_trace)
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertEqual(event.service_event.type, ServiceEvent.CRASH)
    self.assertEqual(event.service_event.stack_trace, stack_trace)

  def test_get_service_event_crash_with_unicode_trace(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    stack_trace = u"Soyez prêt à un étrange goût de Noël."
    log_event = monitoring._get_service_event('CRASH',
                                              stack_trace=stack_trace)
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertEqual(event.service_event.type, ServiceEvent.CRASH)
    self.assertEqual(event.service_event.stack_trace, stack_trace)

  def test_get_service_event_crash_with_big_trace(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    stack_trace = "this is way too long" * 55
    self.assertTrue(len(stack_trace) > monitoring.STACK_TRACE_MAX_SIZE)
    log_event = monitoring._get_service_event('CRASH',
                                              stack_trace=stack_trace)
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertEqual(event.service_event.type, ServiceEvent.CRASH)
    self.assertEqual(len(event.service_event.stack_trace),
                     monitoring.STACK_TRACE_MAX_SIZE)

  def test_get_service_event_crash_invalid_trace(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    # This is not a stacktrace
    stack_trace = 123456
    # Should not crash
    log_event = monitoring._get_service_event('CRASH',
                                              stack_trace=stack_trace)
    event = ChromeInfraEvent.FromString(log_event.source_extension)

    # Send only valid data this time
    self.assertEqual(event.service_event.type, ServiceEvent.CRASH)
    self.assertFalse(event.service_event.HasField('stack_trace'))

  def test_get_service_event_trace_without_crash(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    stack_trace = 'A nice ascii string'
    log_event = monitoring._get_service_event('START',
                                              stack_trace=stack_trace)
    event = ChromeInfraEvent.FromString(log_event.source_extension)

    # Make sure we send even invalid data.
    self.assertEqual(event.service_event.type, ServiceEvent.START)
    self.assertEqual(event.service_event.stack_trace, stack_trace)


  def test_send_service_event_bad_versions(self):
    # Check that an invalid version does not cause any exception.
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    code_version = [{}, {'revision': 'https://fake.url'}]
    log_event = monitoring._get_service_event('START',
                                              code_version=code_version)
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('service_event'))
    self.assertTrue(event.service_event.HasField('type'))
    self.assertEqual(len(event.service_event.code_version), 0)

  def test_send_service_event_bad_type(self):
    # Check that an invalid type for code_version does not raise
    # any exception.

    code_versions = [None, 123, 'string',
                     [None], [123], ['string'], [['list']]]
    for code_version in code_versions:
      log_event = monitoring._get_service_event('START',
                                                code_version=code_version)
      event = ChromeInfraEvent.FromString(log_event.source_extension)
      self.assertTrue(event.HasField('service_event'))
      self.assertTrue(event.service_event.HasField('type'))
      self.assertEqual(len(event.service_event.code_version), 0)

  def test_send_service_event_smoke(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    self.assertTrue(event_mon.send_service_event('START'))
    self.assertTrue(event_mon.send_service_event('START',
                                                 timestamp_kind=None))
    self.assertTrue(event_mon.send_service_event('START',
                                                  timestamp_kind='BEGIN'))
    self.assertTrue(event_mon.send_service_event('STOP',
                                                  timestamp_kind='END',
                                                  event_timestamp=1234))

  def test_send_service_errors(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    self.assertFalse(event_mon.send_service_event('invalid'))
    self.assertFalse(event_mon.send_service_event('START',
                                                   timestamp_kind='invalid'))
    self.assertFalse(event_mon.send_service_event(
      'START', event_timestamp='2015-01-25'))
