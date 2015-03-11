# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import unittest

from infra.libs import event_mon
from infra.libs.event_mon import config, router


class ConfigTest(unittest.TestCase):
  def _set_up_args(self, args=None):
    parser = argparse.ArgumentParser()
    event_mon.add_argparse_options(parser)
    args = parser.parse_args((args or []))
    self.assertEquals(args.event_mon_run_type, 'dry')
    event_mon.process_argparse_options(args)
    r = config._router
    self.assertIsInstance(r, router._Router)
    # Check that process_argparse_options is idempotent
    event_mon.process_argparse_options(args)
    self.assertIs(config._router, r)

  def _close(self):
    event_mon.close()
    # Test that calling it twice does not raise an exception.
    event_mon.close()

  def test_no_args_smoke(self):
    self._set_up_args()
    self._close()

  def test_args_and_default_event(self):
    # The protobuf structure is actually an API not an implementation detail
    # so it's sane to test for changes.
    hostname = 'a'
    service_name = 'b'
    appengine_name = 'c'

    args = ['--event-mon-hostname', hostname,
            '--event-mon-service-name', service_name,
            '--event-mon-appengine-name', appengine_name]
    self._set_up_args(args=args)
    event = config.cache['default_event']
    self.assertEquals(event.event_source.host_name, hostname)
    self.assertEquals(event.event_source.service_name, service_name)
    self.assertEquals(event.event_source.appengine_name, appengine_name)
    self._close()

  def test_default_event(self):
    # The protobuf structure is actually an API not an implementation detail
    # so it's sane to test for changes.
    event_mon.setup_monitoring()
    event = config.cache['default_event']
    self.assertTrue(event.event_source.HasField('host_name'))
    self.assertFalse(event.event_source.HasField('service_name'))
    self.assertFalse(event.event_source.HasField('appengine_name'))

    self._close()

  def test_default_event_with_values(self):
    # The protobuf structure is actually an API not an implementation detail
    # so it's sane to test for changes.
    hostname = 'a'
    service_name = 'b'
    appengine_name = 'c'

    event_mon.setup_monitoring(
      hostname=hostname,
      service_name=service_name,
      appengine_name=appengine_name
    )
    event = config.cache['default_event']
    self.assertEquals(event.event_source.host_name, hostname)
    self.assertEquals(event.event_source.service_name, service_name)
    self.assertEquals(event.event_source.appengine_name, appengine_name)

    self._close()
