# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import unittest

import google.protobuf

import infra_libs
from infra_libs import event_mon

from infra.tools.send_monitoring_event import send_event

from infra_libs.event_mon import (BuildEvent, ServiceEvent,
                                  ChromeInfraEvent, LogRequestLite)

DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')


class SendingEventBaseTest(unittest.TestCase):
  """Base class for all tests that send events."""
  def setUp(self):
    # Use the dry run mode instead of a mock.
    event_mon.setup_monitoring(run_type='dry')

  def tearDown(self):
    event_mon.close()


class TestArgumentParsing(unittest.TestCase):
  def test_smoke(self):
    args = send_event.get_arguments(['--event-mon-service-name', 'thing'])
    self.assertIsInstance(args, argparse.Namespace)
    self.assertEquals(args.event_mon_service_name, 'thing')

  def test_both_build_and_service_flags(self):
    with self.assertRaises(SystemExit):
      send_event.get_arguments(
        ['--build-event-type', 'BUILD', '--service-event-type', 'START'])

  def test_both_from_file_and_build(self):
    with self.assertRaises(SystemExit):
      send_event.get_arguments(
        ['--build-event-type', 'BUILD', '--events-from-file', 'filename'])

  def test_both_from_file_and_service(self):
    with self.assertRaises(SystemExit):
      send_event.get_arguments(
        ['--service-event-type', 'START', '--events-from-file', 'filename'])

  def test_extra_result_code_string(self):
    args = send_event.get_arguments(
        ['--service-event-type', 'START',
         '--build-event-extra-result-code', 'test-string'])
    self.assertEquals(args.build_event_extra_result_code, 'test-string')

  def test_extra_result_code_strings_list(self):
    args = send_event.get_arguments(
        ['--service-event-type', 'START',
         '--build-event-extra-result-code', 'code1,code2,code3'])
    self.assertEquals(args.build_event_extra_result_code,
                      ['code1', 'code2', 'code3'])

  def test_extra_result_code_json(self):
    args = send_event.get_arguments(
        ['--service-event-type', 'START',
         '--build-event-extra-result-code', '["code4", "code5","code6"]'])
    self.assertEquals(args.build_event_extra_result_code,
                      ['code4', 'code5', 'code6'])


class TestServiceEvent(SendingEventBaseTest):
  def test_send_service_event_stack_trace_smoke(self):
    args = send_event.get_arguments(
      ['--event-mon-service-name', 'thing',
       '--service-event-stack-trace', 'stack trace'])
    send_event.send_service_event(args)

  def test_send_service_event_revinfo_smoke(self):
    args = send_event.get_arguments(
      ['--event-mon-service-name', 'thing',
       '--service-event-type', 'START',
       '--service-event-revinfo', os.path.join(DATA_DIR, 'revinfo.txt')])
    send_event.send_service_event(args)


class TestBuildEvent(SendingEventBaseTest):
  def test_send_build_event_smoke(self):
    args = send_event.get_arguments(
      ['--event-mon-service-name', 'thing',
       '--build-event-type', 'SCHEDULER',
       '--build-event-hostname', 'foo.bar.dns',
       '--build-event-build-name', 'whatever'])
    self.assertTrue(send_event.send_build_event(args))

  def test_send_build_event_smoke_missing_goma_file(self):
    args = send_event.get_arguments(
      ['--event-mon-service-name', 'thing',
       '--build-event-type', 'BUILD',
       '--build-event-hostname', 'foo.bar.dns',
       '--build-event-build-name', 'whatever',
       '--build-event-goma-stats-path',
           os.path.join(DATA_DIR, 'this-file-does-not-exist')])
    with self.assertRaises(IOError):
      send_event.send_build_event(args)


class TestInputModesFile(unittest.TestCase):
  # Test the various ways to pass information to send_monitoring_event
  # TODO(pgervais): test precedence order.
  def tearDown(self):
    event_mon.close()

  def test_send_build_event_with_goma_stats(self):
    # Write a file to avoid mocks
    with infra_libs.temporary_directory(prefix='send_event_test-') as tmpdir:
      outfile = os.path.join(tmpdir, 'out.bin')
      args = send_event.get_arguments(
        ['--event-mon-run-type', 'file',
         '--event-mon-output-file', outfile,
         '--event-mon-service-name', 'thing',
         '--build-event-type', 'BUILD',
         '--build-event-hostname', 'foo.bar.dns',
         '--build-event-build-name', 'whatever',
         '--build-event-goma-stats-path',
         os.path.join(DATA_DIR, 'goma_stats.bin')])
      self.assertEquals(args.event_mon_run_type, 'file')
      event_mon.process_argparse_options(args)
      self.assertTrue(send_event.send_build_event(args))

      # Now open the resulting file and check what was written
      with open(outfile, 'rb') as f:
        request = LogRequestLite.FromString(f.read())

    self.assertEqual(len(request.log_event), 1)
    event = ChromeInfraEvent.FromString(request.log_event[0].source_extension)
    self.assertEqual(event.build_event.goma_stats.request_stats.total, 10)
    self.assertEqual(event.build_event.goma_stats.request_stats.success, 9)
    self.assertEqual(event.build_event.goma_stats.request_stats.failure, 1)
    self.assertEqual(event.build_event.host_name, 'foo.bar.dns')

  def test_send_build_event_with_invalid_goma_stats(self):
    # Write a file to avoid mocks
    with infra_libs.temporary_directory(prefix='send_event_test-') as tmpdir:
      outfile = os.path.join(tmpdir, 'out.bin')
      args = send_event.get_arguments(
        ['--event-mon-run-type', 'file',
         '--event-mon-output-file', outfile,
         '--event-mon-service-name', 'thing',
         '--build-event-type', 'BUILD',
         '--build-event-hostname', 'foo.bar.dns',
         '--build-event-build-name', 'whatever',
         '--build-event-goma-stats-path',
         os.path.join(DATA_DIR, 'garbage')])
      self.assertEquals(args.event_mon_run_type, 'file')
      event_mon.process_argparse_options(args)
      with self.assertRaises(google.protobuf.message.DecodeError):
        send_event.send_build_event(args)

  # The default event used below (build-foo-builder.bin) has been generated by:
  # ./run.py infra.tools.send_monitoring_event \
  #     --event-mon-run-type=file \
  #     --event-mon-output-file=./build-foo-builder.bin \
  #     --build-event-hostname=myhostname \
  #     --event-mon-timestamp-kind=BEGIN \
  #     --event-mon-event-timestamp=123 \
  #     --build-event-type=BUILD \
  #     --build-event-build-name=foo"
  def test_logrequest_path_valid_build_event(self):
    with infra_libs.temporary_directory(prefix='send_event_test-') as tmpdir:
      outfile = os.path.join(tmpdir, 'out.bin')
      args = send_event.get_arguments(
        ['--event-mon-run-type', 'file',
         '--event-mon-output-file', outfile,
         '--event-mon-service-name', 'thing',
         '--event-logrequest-path',
             os.path.join(DATA_DIR, 'build-foo-builder.bin'),
         '--build-event-build-number', '3'
        ])
      self.assertEquals(args.event_mon_run_type, 'file')
      event_mon.process_argparse_options(args)
      send_event._process_logrequest_path(args)
      self.assertTrue(send_event.send_build_event(args))

      # Now open the resulting file and check what was written
      with open(outfile, 'rb') as f:
        request = LogRequestLite.FromString(f.read())

    self.assertEqual(len(request.log_event), 1)
    event = ChromeInfraEvent.FromString(request.log_event[0].source_extension)
    self.assertEqual(event.build_event.host_name, 'myhostname')
    self.assertEqual(event.build_event.build_number, 3)
    self.assertEqual(event.timestamp_kind, ChromeInfraEvent.BEGIN)

  def test_logrequest_path_build_type_override(self):
    # logrequest contains build event, overrid the type with an arg.
    with infra_libs.temporary_directory(prefix='send_event_test-') as tmpdir:
      outfile = os.path.join(tmpdir, 'out.bin')
      args = send_event.get_arguments(
        ['--event-mon-run-type', 'file',
         '--event-mon-output-file', outfile,
         '--event-mon-service-name', 'thing',
         '--event-logrequest-path',
             os.path.join(DATA_DIR, 'build-foo-builder.bin'),
         '--build-event-build-number', '3',
         '--build-event-type', 'STEP',
        ])
      self.assertEquals(args.event_mon_run_type, 'file')
      event_mon.process_argparse_options(args)
      send_event._process_logrequest_path(args)
      self.assertTrue(send_event.send_build_event(args))

      # Now open the resulting file and check what was written
      with open(outfile, 'rb') as f:
        request = LogRequestLite.FromString(f.read())

    self.assertEqual(len(request.log_event), 1)
    event = ChromeInfraEvent.FromString(request.log_event[0].source_extension)
    self.assertEqual(event.build_event.host_name, 'myhostname')
    self.assertEqual(event.build_event.type, BuildEvent.STEP)
    self.assertEqual(event.build_event.build_number, 3)
    self.assertEqual(event.timestamp_kind, ChromeInfraEvent.BEGIN)

  def test_logrequest_path_build_service_conflicts(self):
    # logrequest contains build event, provides service event as arg
    with infra_libs.temporary_directory(prefix='send_event_test-') as tmpdir:
      outfile = os.path.join(tmpdir, 'out.bin')
      args = send_event.get_arguments(
        ['--event-mon-run-type', 'file',
         '--event-mon-output-file', outfile,
         '--event-mon-service-name', 'thing',
         '--event-logrequest-path',
             os.path.join(DATA_DIR, 'build-foo-builder.bin'),
         '--build-event-build-number', '3',
         '--service-event-type', 'START',
        ])
      self.assertEquals(args.event_mon_run_type, 'file')
      event_mon.process_argparse_options(args)
      with self.assertRaises(ValueError):
        send_event._process_logrequest_path(args)

  # The default event used below has been generated using:
  # ./run.py infra.tools.send_monitoring_event
  #     --event-mon-run-type=file
  #     --event-mon-output-file=./service-bar-service.bin
  #     --service-event-type=START
  #     --event-mon-service-name=bar
  #     --event-mon-hostname=myhostname
  #     --event-mon-timestamp-kind=BEGIN
  #     --event-mon-event-timestamp=123
  def test_logrequest_path_valid_service_event(self):
    with infra_libs.temporary_directory(prefix='send_event_test-') as tmpdir:
      outfile = os.path.join(tmpdir, 'out.bin')
      args = send_event.get_arguments(
        ['--event-mon-run-type', 'file',
         '--event-mon-output-file', outfile,
         '--event-mon-service-name', 'thing',
         '--event-logrequest-path',
             os.path.join(DATA_DIR, 'service-bar-service.bin'),
        ])
      self.assertEquals(args.event_mon_run_type, 'file')
      event_mon.process_argparse_options(args)
      send_event._process_logrequest_path(args)
      self.assertTrue(send_event.send_service_event(args))

      # Now open the resulting file and check what was written
      with open(outfile, 'rb') as f:
        request = LogRequestLite.FromString(f.read())

    self.assertEqual(len(request.log_event), 1)
    event = ChromeInfraEvent.FromString(request.log_event[0].source_extension)
    self.assertEqual(event.event_source.host_name, 'myhostname')
    self.assertEqual(event.service_event.type, ServiceEvent.START)
    self.assertEqual(event.timestamp_kind, ChromeInfraEvent.BEGIN)

  def test_logrequest_path_service_type_override(self):
    with infra_libs.temporary_directory(prefix='send_event_test-') as tmpdir:
      outfile = os.path.join(tmpdir, 'out.bin')
      args = send_event.get_arguments(
        ['--event-mon-run-type', 'file',
         '--event-mon-output-file', outfile,
         '--event-mon-service-name', 'thing',
         '--event-logrequest-path',
             os.path.join(DATA_DIR, 'service-bar-service.bin'),
         '--service-event-type', 'STOP',
        ])
      self.assertEquals(args.event_mon_run_type, 'file')
      event_mon.process_argparse_options(args)
      send_event._process_logrequest_path(args)
      self.assertTrue(send_event.send_service_event(args))

      # Now open the resulting file and check what was written
      with open(outfile, 'rb') as f:
        request = LogRequestLite.FromString(f.read())

    self.assertEqual(len(request.log_event), 1)
    event = ChromeInfraEvent.FromString(request.log_event[0].source_extension)
    self.assertEqual(event.event_source.host_name, 'myhostname')
    self.assertEqual(event.service_event.type, ServiceEvent.STOP)
    self.assertEqual(event.timestamp_kind, ChromeInfraEvent.END)

  def test_logrequest_path_service_build_conflict(self):
    with infra_libs.temporary_directory(prefix='send_event_test-') as tmpdir:
      outfile = os.path.join(tmpdir, 'out.bin')
      args = send_event.get_arguments(
        ['--event-mon-run-type', 'file',
         '--event-mon-output-file', outfile,
         '--event-mon-service-name', 'thing',
         '--event-logrequest-path',
             os.path.join(DATA_DIR, 'service-bar-service.bin'),
         '--build-event-type', 'BUILD',
        ])
      self.assertEquals(args.event_mon_run_type, 'file')
      event_mon.process_argparse_options(args)
      with self.assertRaises(ValueError):
        send_event._process_logrequest_path(args)

  def test_logrequest_path_service_build_and_service(self):
    # The logrequest provided contains both a service and a build type,
    # which is invalid.
    with infra_libs.temporary_directory(prefix='send_event_test-') as tmpdir:
      outfile = os.path.join(tmpdir, 'out.bin')
      args = send_event.get_arguments(
        ['--event-mon-run-type', 'file',
         '--event-mon-output-file', outfile,
         '--event-mon-service-name', 'thing',
         '--event-logrequest-path',
             os.path.join(DATA_DIR, 'build-and-service-event.bin'),
        ])
      self.assertEquals(args.event_mon_run_type, 'file')
      event_mon.process_argparse_options(args)
      with self.assertRaises(ValueError):
        send_event._process_logrequest_path(args)


class TestEventsFromTextFile(SendingEventBaseTest):
  def test_send_events_from_file_smoke(self):
    # Create a temporary file because we don't want to risk deleting a
    # checked-in file.
    with infra_libs.temporary_directory(prefix='send-events-test') as tempdir:
      event_file = os.path.join(tempdir, 'events.log')
      with open(event_file, 'w') as f:
        f.write('{"build-event-type": "STEP", '
                '"build-event-build-name": "infra-continuous-precise-64", '
                '"event-mon-service-name": "buildbot/master/chromium.infra", '
                '"build-event-step-number": 9, '
                '"build-event-build-number": 5, '
                '"event-mon-timestamp-kind": "END", '
                '"build-event-step-name": "cipd - test packages integrity", '
                '"build-event-build-scheduling-time": 1434665160000, '
                '"build-event-hostname": "vm25-m1"}\n')

      self.assertTrue(os.path.isfile(event_file))
      args = send_event.get_arguments(['--events-from-file', event_file])
      send_event.send_events_from_file(args)
      self.assertTrue(os.path.isfile(event_file))

  def test_send_events_from_file_delete_file_smoke(self):
    # Create a temporary file because we don't want to risk deleting a
    # checked-in file.
    with infra_libs.temporary_directory(prefix='send-events-test-') as tempdir:
      event_file = os.path.join(tempdir, 'events.log')
      with open(event_file, 'w') as f:
        f.write('{"build-event-type": "STEP", '
                '"build-event-build-name": "infra-continuous-precise-64", '
                '"event-mon-service-name": "buildbot/master/chromium.infra", '
                '"build-event-step-number": 9, '
                '"build-event-build-number": 5, '
                '"event-mon-timestamp-kind": "END", '
                '"build-event-step-name": "cipd - test packages integrity", '
                '"build-event-build-scheduling-time": 1434665160000, '
                '"build-event-hostname": "vm25-m1"}\n')
      self.assertTrue(os.path.isfile(event_file))
      args = send_event.get_arguments(['--events-from-file', event_file,
                                       '--delete-file-when-sent'])
      send_event.send_events_from_file(args)
      self.assertFalse(os.path.isfile(event_file))


class TestReadEventsFromFile(SendingEventBaseTest):
  def test_read_valid_file(self):
    events = send_event.read_events_from_file(
      os.path.join(DATA_DIR, 'events_valid.log'))
    for event in events:
      self.assertIsInstance(event, event_mon.Event)
    self.assertEqual(len(events), 5)

  def test_read_invalid_file(self):
    events = send_event.read_events_from_file(
      os.path.join(DATA_DIR, 'events_invalid.log'))
    for event in events:
      self.assertIsInstance(event, event_mon.Event)

    self.assertEqual(len(events), 4)

  def test_read_file_with_blank_lines(self):
    events = send_event.read_events_from_file(
      os.path.join(DATA_DIR, 'events_blank_lines.log'))
    for event in events:
      self.assertIsInstance(event, event_mon.Event)

    self.assertEqual(len(events), 5)

  def test_read_file_with_service_event(self):
    # service_event is not supported (yet).
    events = send_event.read_events_from_file(
      os.path.join(DATA_DIR, 'events_one_service_event.log'))
    for event in events:
      self.assertIsInstance(event, event_mon.Event)

    self.assertEqual(len(events), 4)

  def test_read_with_extra_result_code(self):
    events = send_event.read_events_from_file(
      os.path.join(DATA_DIR, 'events_valid_extra_result.log'))
    for event in events:
      self.assertIsInstance(event, event_mon.Event)
    self.assertEqual(len(events), 1)
    self.assertEqual(
      len(events[0].proto.build_event.extra_result_code), 1)


class TestGetEventsFileList(unittest.TestCase):
  FILES_DIR = os.path.join(DATA_DIR, 'get_events_file_list')
  def test_no_filename(self):
    file_list = send_event.get_event_file_list([])
    self.assertTrue(len(file_list) == 0)

  def test_one_filename(self):
    file_list = send_event.get_event_file_list(
      [os.path.join(self.FILES_DIR, 'events.log')])
    self.assertTrue(len(file_list) == 1)
    self.assertTrue(file_list[0].endswith('events.log'))

  def test_two_filenames(self):
    filenames = ('events.log', 'events-2.log')
    file_list = send_event.get_event_file_list(
      [os.path.join(self.FILES_DIR, filename) for filename in filenames])
    self.assertTrue(len(file_list) == 2)
    for fname in file_list:
      self.assertTrue(any(fname.endswith(filename) for filename in filenames))

  def test_one_wildcard(self):
    filenames = ('events.log', 'events-1.log', 'events-2.log')
    file_list = send_event.get_event_file_list(
      [os.path.join(self.FILES_DIR, 'events*.log')])
    self.assertTrue(len(file_list) == 3)
    for fname in file_list:
      self.assertTrue(any(fname.endswith(filename) for filename in filenames))

  def test_one_wildcard_one_file(self):
    filenames = ('events.log', 'events-1.log', 'events-2.log')
    file_list = send_event.get_event_file_list(
      [os.path.join(self.FILES_DIR, 'events-?.log'),
       os.path.join(self.FILES_DIR, 'events.log')])
    self.assertTrue(len(file_list) == 3)
    for fname in file_list:
      self.assertTrue(any(fname.endswith(filename) for filename in filenames))


class TestProcessRequestPath(SendingEventBaseTest):
  def test_logrequest_missing_args(self):
    orig_event = event_mon.get_default_event()
    self.assertIsNot(orig_event, None)

    args = argparse.Namespace()
    args.event_logrequest_path = None
    send_event._process_logrequest_path(args)

    self.assertEqual(orig_event, event_mon.get_default_event())

  def test_logrequest_with_valid_file(self):
    orig_event = event_mon.get_default_event()
    self.assertIsNot(orig_event, None)

    args = argparse.Namespace()
    args.event_logrequest_path = os.path.join(DATA_DIR, 'logrequest-build.bin')
    args.service_event_type = None
    args.build_event_type = None
    send_event._process_logrequest_path(args)

    new_event = event_mon.get_default_event()
    self.assertNotEqual(orig_event, new_event)
    self.assertEqual(new_event.build_event.type, BuildEvent.BUILD)

  def test_logrequest_with_no_log_event(self):
    orig_event = event_mon.get_default_event()
    self.assertIsNot(orig_event, None)

    args = argparse.Namespace()
    args.event_logrequest_path = os.path.join(DATA_DIR, 'logrequest-empty.bin')
    with self.assertRaises(ValueError):
      send_event._process_logrequest_path(args)

  def test_logrequest_with_bad_content(self):
    orig_event = event_mon.get_default_event()
    self.assertIsNot(orig_event, None)

    args = argparse.Namespace()
    args.event_logrequest_path = os.path.join(DATA_DIR, 'garbage')
    with self.assertRaises(google.protobuf.message.DecodeError):
      send_event._process_logrequest_path(args)

  def test_logrequest_with_missing_file(self):
    args = argparse.Namespace()
    args.event_logrequest_path = os.path.join(DATA_DIR, 'non-existent-file.bin')
    with self.assertRaises(IOError):
      send_event._process_logrequest_path(args)
