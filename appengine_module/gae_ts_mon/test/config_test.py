# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

import gae_ts_mon
import mock

from infra_libs.ts_mon import config
from infra_libs.ts_mon import memcache_metric_store
from infra_libs.ts_mon.common import monitors
from infra_libs.ts_mon.common.test import stubs
from testing_utils import testing


class ConfigTest(testing.AppengineTestCase):
  def setUp(self):
    super(ConfigTest, self).setUp()

    self.mock_state = stubs.MockState()
    mock.patch('infra_libs.ts_mon.common.interface.state',
        new=self.mock_state).start()

    mock.patch('infra_libs.ts_mon.memcache_metric_store.MemcacheMetricStore',
               autospec=True).start()
    mock.patch('infra_libs.ts_mon.common.monitors.PubSubMonitor',
               autospec=True).start()

  def tearDown(self):
    super(ConfigTest, self).tearDown()

    mock.patch.stopall()

  def test_sets_target(self):
    config.initialize()

    self.assertEqual('testbed-test', self.mock_state.target.service_name)
    self.assertEqual('default', self.mock_state.target.job_name)
    self.assertEqual('appengine', self.mock_state.target.region)
    self.assertEqual('testbed', self.mock_state.target.hostname)

  def test_sets_monitor(self):
    os.environ['SERVER_SOFTWARE'] = 'Production'  # != 'Development'

    config.initialize()

    self.assertEquals(1, monitors.PubSubMonitor.call_count)

  def test_sets_monitor_dev(self):
    config.initialize()

    self.assertFalse(monitors.PubSubMonitor.called)
    self.assertIsInstance(self.mock_state.global_monitor, monitors.DebugMonitor)

  def test_already_configured(self):
    self.mock_state.global_monitor = monitors.DebugMonitor()
    self.mock_state.store = memcache_metric_store.MemcacheMetricStore(
        self.mock_state)

    config.initialize()

    self.mock_state.store.update_metric_index.assert_called_once_with()
    self.assertIsNone(self.mock_state.target)
