# -*- encoding:utf-8 -*-
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import unittest
import zlib

from infra_libs import event_mon
from infra_libs.event_mon import config, router
from infra_libs.event_mon import monitoring
from infra_libs.event_mon.chrome_infra_log_pb2 import ChromeInfraEvent
from infra_libs.event_mon.chrome_infra_log_pb2 import ServiceEvent
from infra_libs.event_mon.chrome_infra_log_pb2 import BuildEvent
from infra_libs.event_mon.goma_stats_pb2 import GomaStats
from infra_libs.event_mon.log_request_lite_pb2 import LogRequestLite


class ConstantTest(unittest.TestCase):
  def test_constants(self):
    # Make sure constants have not been renamed since they're part of the API.
    self.assertTrue(event_mon.EVENT_TYPES)
    self.assertTrue(event_mon.TIMESTAMP_KINDS)
    self.assertTrue(event_mon.BUILD_EVENT_TYPES)
    self.assertTrue(event_mon.BUILD_RESULTS)


class GetServiceEventTest(unittest.TestCase):

  # We have to setup and tear down event_mon for each test to avoid
  # interactions between tests because event_mon stores a global state.
  def setUp(self):
    event_mon.setup_monitoring(run_type='dry')

  def tearDown(self):
    event_mon.close()

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

  def test_get_service_event_with_non_default_service_name(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    log_event = monitoring._get_service_event(
      'START', service_name='my.nice.service.name')
    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)
    self.assertTrue(log_event.HasField('event_time_ms'))
    self.assertTrue(log_event.HasField('source_extension'))

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('service_event'))
    self.assertTrue(event.service_event.HasField('type'))
    self.assertEquals(event.service_event.type, ServiceEvent.START)
    self.assertEquals(event.event_source.service_name, 'my.nice.service.name')

  def test_get_service_event_with_unicode_service_name(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)
    service_name = u'à_la_française_hé_oui'
    log_event = monitoring._get_service_event(
      'START', service_name=service_name)
    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)
    self.assertTrue(log_event.HasField('event_time_ms'))
    self.assertTrue(log_event.HasField('source_extension'))

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('service_event'))
    self.assertTrue(event.service_event.HasField('type'))
    self.assertEquals(event.service_event.type, ServiceEvent.START)
    self.assertEquals(event.event_source.service_name, service_name)


class SendServiceEventTest(unittest.TestCase):
  def setUp(self):
    event_mon.setup_monitoring(run_type='dry')

  def tearDown(self):
    event_mon.close()

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


class GetBuildEventTest(unittest.TestCase):
  def setUp(self):
    event_mon.setup_monitoring(run_type='dry')

  def tearDown(self):
    event_mon.close()

  def test_get_build_event_default(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    log_event = monitoring.get_build_event('BUILD', hostname, build_name)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)
    self.assertTrue(log_event.HasField('event_time_ms'))
    self.assertTrue(log_event.HasField('source_extension'))

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)

  def test_get_build_event_invalid_type(self):
    # An invalid type is a critical error.
    log_event = monitoring.get_build_event('INVALID_TYPE',
                                            'bot.host.name',
                                            'build_name')
    self.assertIsNone(log_event)

  def test_get_build_event_invalid_build_name(self):
    # an invalid builder name is not a critical error.
    hostname = 'bot.host.name'
    log_event = monitoring.get_build_event('BUILD', hostname, '')
    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)

    self.assertFalse(event.build_event.HasField('build_name'))

  def test_get_build_event_invalid_hostname(self):
    # an invalid hostname is not a critical error.
    builder_name = 'builder_name'
    log_event = monitoring.get_build_event('BUILD', None, builder_name)
    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.build_name, builder_name)

    self.assertFalse(event.build_event.HasField('host_name'))

  def test_get_build_event_with_build_zero(self):
    # testing 0 is important because bool(0) == False
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 0
    build_scheduling_time = 123456789
    log_event = monitoring.get_build_event(
      'BUILD',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)

  def test_get_build_event_with_build_non_zero(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265  # int32
    build_scheduling_time = 123456789
    log_event = monitoring.get_build_event(
      'BUILD',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)

  def test_get_build_event_invalid_scheduler(self):
    # Providing a build number on a scheduler event is invalid.
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265  # int32
    log_event = monitoring.get_build_event(
      'SCHEDULER',
      hostname,
      build_name,
      build_number=build_number)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.SCHEDULER)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)

    self.assertFalse(event.build_event.HasField('build_scheduling_time_ms'))

  def test_get_build_event_invalid_buildname(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265  # int32
    build_scheduling_time = 123456789
    log_event = monitoring.get_build_event(
      'BUILD',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)

  def test_get_build_event_missing_build_number(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_scheduling_time = 123456789
    log_event = monitoring.get_build_event(
      'BUILD',
      hostname,
      build_name,
      build_scheduling_time=build_scheduling_time)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)

    self.assertFalse(event.build_event.HasField('build_number'))

  def test_get_build_event_with_step_info_wrong_type(self):
    # BUILD event with step info is invalid.
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789
    step_name = 'step_name'
    step_number = 0  # valid step number

    log_event = monitoring.get_build_event(
      'BUILD',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      step_name=step_name,
      step_number=step_number)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)
    self.assertEquals(event.build_event.step_name, step_name)
    self.assertEquals(event.build_event.step_number, step_number)

  def test_get_build_event_with_step_info(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789
    step_name = 'step_name'
    step_number = 0  # valid step number

    log_event = monitoring.get_build_event(
      'STEP',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      step_name=step_name,
      step_number=step_number)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.STEP)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)
    self.assertEquals(event.build_event.step_name, step_name)
    self.assertEquals(event.build_event.step_number, step_number)

  def test_get_build_event_missing_step_name(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789
    step_number = 0  # valid step number

    log_event = monitoring.get_build_event(
      'STEP',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      step_number=step_number)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.STEP)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)
    self.assertEquals(event.build_event.step_number, step_number)

    self.assertFalse(event.build_event.HasField('step_name'))

  def test_get_build_event_missing_step_number(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789
    step_name = 'step_name'

    log_event = monitoring.get_build_event(
      'STEP',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      step_name=step_name)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.STEP)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)
    self.assertEquals(event.build_event.step_name, step_name)

    self.assertFalse(event.build_event.HasField('step_number'))

  def test_get_build_event_step_info_missing_build_info(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    step_name = 'step_name'
    step_number = 0  # valid step number

    log_event = monitoring.get_build_event(
      'STEP',
      hostname,
      build_name,
      step_name=step_name,
      step_number=step_number)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.STEP)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.step_name, step_name)
    self.assertEquals(event.build_event.step_number, step_number)

    self.assertFalse(event.build_event.HasField('build_number'))
    self.assertFalse(event.build_event.HasField('build_scheduling_time_ms'))

  def test_get_build_event_with_invalid_result(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789
    result = '---INVALID---'

    log_event = monitoring.get_build_event(
      'BUILD',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      result=result)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)

    self.assertFalse(event.build_event.HasField('result'))

  def test_get_build_event_with_valid_result(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789
    result = 'SUCCESS'

    log_event = monitoring.get_build_event(
      'BUILD',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      result=result)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)
    self.assertEquals(event.build_event.result, BuildEvent.SUCCESS)

  def test_get_build_event_test_result_mapping(self):
    # Tests the hacky mapping between buildbot results and the proto values.
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789

    # WARNINGS -> WARNING
    log_event = monitoring.get_build_event(
      'BUILD',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      result='WARNINGS')  # with an S

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)
    self.assertEquals(event.build_event.result, BuildEvent.WARNING) # no S

    # EXCEPTION -> INFRA_FAILURE
    log_event = monitoring.get_build_event(
      'BUILD',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      result='EXCEPTION')

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)
    self.assertEquals(event.build_event.result, BuildEvent.INFRA_FAILURE)

  def test_get_build_event_valid_result_wrong_type(self):
    # SCHEDULER can't have a result
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789
    result = 'SUCCESS'

    log_event = monitoring.get_build_event(
      'SCHEDULER',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      result=result)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.SCHEDULER)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)
    self.assertEquals(event.build_event.result, BuildEvent.SUCCESS)

  def test_get_build_event_invalid_goma_stats(self):
    # SCHEDULER can't have a result
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789
    step_name = 'compile'
    goma_stats_gz = base64.b64encode(zlib.compress('invalid goma_stats'))

    log_event = monitoring.get_build_event(
      'STEP',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      step_name=step_name,
      goma_stats_gz=goma_stats_gz)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.STEP)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)

    self.assertFalse(event.build_event.HasField('goma_stats'))
    #self.assertFalse(event.build_event.goma_stats.IsInitialized())

  def test_get_build_event_valid_goma_stats(self):
    # SCHEDULER can't have a result
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789
    step_name = 'compile'
    goma_stats = GomaStats()
    goma_stats_gz = base64.b64encode(
        zlib.compress(goma_stats.SerializeToString()))

    log_event = monitoring.get_build_event(
      'STEP',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      step_name=step_name,
      goma_stats_gz=goma_stats_gz)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.STEP)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)
    self.assertEquals(event.build_event.goma_stats, goma_stats)

  def test_get_build_event_valid_goma_stats_wrong_type(self):
    # SCHEDULER can't have a result
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789
    goma_stats = GomaStats()
    goma_stats_gz = base64.b64encode(
        zlib.compress(goma_stats.SerializeToString()))

    log_event = monitoring.get_build_event(
      'SCHEDULER',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      goma_stats_gz=goma_stats_gz)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.SCHEDULER)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)
    self.assertEquals(event.build_event.goma_stats, goma_stats)

  def test_get_build_event_valid_goma_stats_wrong_step_name(self):
    # SCHEDULER can't have a result
    hostname = 'bot.host.name'
    build_name = 'build_name'
    build_number = 314159265
    build_scheduling_time = 123456789
    step_name = 'invalid'
    goma_stats = GomaStats()
    goma_stats_gz = base64.b64encode(
        zlib.compress(goma_stats.SerializeToString()))

    log_event = monitoring.get_build_event(
      'STEP',
      hostname,
      build_name,
      build_number=build_number,
      build_scheduling_time=build_scheduling_time,
      step_name=step_name,
      goma_stats_gz=goma_stats_gz)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.STEP)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.build_event.build_number, build_number)
    self.assertEquals(event.build_event.build_scheduling_time_ms,
                      build_scheduling_time)
    self.assertEquals(event.build_event.goma_stats, goma_stats)

  def test_get_build_event_with_non_default_service_name(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    service_name = 'my.other.nice.service'
    log_event = monitoring.get_build_event(
      'BUILD', hostname, build_name, service_name=service_name)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)
    self.assertTrue(log_event.HasField('event_time_ms'))
    self.assertTrue(log_event.HasField('source_extension'))

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.event_source.service_name, service_name)

  def test_get_build_event_with_unicode_service_name(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    service_name = u'à_la_française'
    log_event = monitoring.get_build_event(
      'BUILD', hostname, build_name, service_name=service_name)

    self.assertIsInstance(log_event, LogRequestLite.LogEventLite)
    self.assertTrue(log_event.HasField('event_time_ms'))
    self.assertTrue(log_event.HasField('source_extension'))

    # Check that source_extension deserializes to the right thing.
    event = ChromeInfraEvent.FromString(log_event.source_extension)
    self.assertTrue(event.HasField('build_event'))
    self.assertEquals(event.build_event.type, BuildEvent.BUILD)
    self.assertEquals(event.build_event.host_name, hostname)
    self.assertEquals(event.build_event.build_name, build_name)
    self.assertEquals(event.event_source.service_name, service_name)

  def test_get_build_event_with_invalid_service_name(self):
    hostname = 'bot.host.name'
    build_name = 'build_name'
    service_name = 1234  # invalid
    log_event = monitoring.get_build_event(
      'BUILD', hostname, build_name, service_name=service_name)

    self.assertIsNone(log_event)


class SendBuildEventTest(unittest.TestCase):
  def setUp(self):
    event_mon.setup_monitoring(run_type='dry')

  def tearDown(self):
    event_mon.close()

  def test_send_build_event_smoke(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    self.assertTrue(event_mon.send_build_event('BUILD',
                                               'bot.host.name',
                                               'build.name'))
    self.assertTrue(event_mon.send_build_event(
      'BUILD',
      'bot.host.name',
      'build_name',
      build_number=1,
      build_scheduling_time=123456789,
      result='FAILURE',
      timestamp_kind='POINT',
      event_timestamp=None))


class SendEventsTest(unittest.TestCase):
  def setUp(self):
    event_mon.setup_monitoring(run_type='dry')

  def tearDown(self):
    event_mon.close()

  def test_send_events_smoke(self):
    self.assertIsInstance(config._router, router._Router)
    self.assertIsInstance(config.cache.get('default_event'), ChromeInfraEvent)

    log_events = [
      event_mon.get_build_event(
        'BUILD',
        'bot.host.name',
        'build_name',
        build_number=1,
        build_scheduling_time=123456789,
        result='FAILURE',
        timestamp_kind='POINT',
        event_timestamp=None),
      event_mon.get_build_event(
        'BUILD',
        'bot2.host.name',
        'build_name2',
        build_number=1,
        build_scheduling_time=123456789,
        result='FAILURE',
        timestamp_kind='POINT',
        event_timestamp=None),
    ]
    self.assertTrue(monitoring.send_events(log_events))
