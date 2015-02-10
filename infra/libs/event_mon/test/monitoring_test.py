# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import unittest

from infra.libs import event_mon
from infra.libs.event_mon import config, router


class MonitoringTest(unittest.TestCase):

  def _set_up_args(self, args=None):
    parser = argparse.ArgumentParser()
    event_mon.add_argparse_options(parser)
    args = parser.parse_args((args or []))
    self.assertEquals(args.event_mon_run_type, 'dry')
    event_mon.process_argparse_options(args)
    self.assertIsInstance(config._router, router._Router)

  def tearDown(self):
    event_mon.close()

  def test_send_service_smoke(self):
    self._set_up_args()
    self.assertTrue(event_mon.send_service_event('START'))
    self.assertTrue(event_mon.send_service_event('START',
                                                 timestamp_kind=None))
    self.assertTrue(event_mon.send_service_event('START',
                                                  timestamp_kind='BEGIN'))
    self.assertTrue(event_mon.send_service_event('STOP',
                                                  timestamp_kind='END',
                                                  event_timestamp=1234))

  def test_send_service_errors(self):
    self._set_up_args()
    self.assertFalse(event_mon.send_service_event('invalid'))
    self.assertFalse(event_mon.send_service_event('START',
                                                   timestamp_kind='invalid'))
    self.assertFalse(event_mon.send_service_event(
      'START', event_timestamp='2015-01-25'))
