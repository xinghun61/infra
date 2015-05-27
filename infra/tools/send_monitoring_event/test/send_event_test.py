# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import unittest

from infra_libs import event_mon
from infra.tools.send_monitoring_event import send_event


DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')


class TestArgumentParsing(unittest.TestCase):
  def test_smoke(self):
    args = send_event.get_arguments(['--event-mon-service-name', 'thing'])
    self.assertIsInstance(args, argparse.Namespace)
    self.assertEquals(args.event_mon_service_name, 'thing')

  def test_invalid_combination(self):
    with self.assertRaises(SystemExit):
      send_event.get_arguments(
        ['--build-event-type', 'BUILD', '--service-event-type', 'START'])


class TestServiceEvent(unittest.TestCase):
  def setUp(self):
    event_mon.setup_monitoring(run_type='dry')

  def tearDown(self):
    event_mon.close()

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


class TestBuildEvent(unittest.TestCase):
  def setUp(self):
    event_mon.setup_monitoring(run_type='dry')

  def tearDown(self):
    event_mon.close()

  def test_send_build_event_smoke(self):
    args = send_event.get_arguments(
      ['--event-mon-service-name', 'thing',
       '--build-event-type', 'SCHEDULER',
       '--build-event-hostname', 'foo.bar.dns',
       '--build-event-build-name', 'whatever'])
    send_event.send_build_event(args)
