# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import unittest

import infra_libs
from infra_libs import event_mon
from infra.tools.send_monitoring_event import send_event


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
    send_event.send_build_event(args)


class TestEventsFromFile(SendingEventBaseTest):
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
