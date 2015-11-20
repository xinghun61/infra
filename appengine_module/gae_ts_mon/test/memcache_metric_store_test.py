# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import gae_ts_mon
import mock

from google.appengine.ext import testbed
from google.appengine.api.memcache import memcache_service_pb

from infra_libs.ts_mon import memcache_metric_store
from infra_libs.ts_mon.common import errors
from infra_libs.ts_mon.common import targets
from infra_libs.ts_mon.common.test import metric_store_test
from testing_utils import testing


class MemcacheMetricStoreTest(metric_store_test.MetricStoreTestBase,
                              testing.AppengineTestCase):
  METRIC_STORE_CLASS = memcache_metric_store.MemcacheMetricStore

  def setUp(self):
    super(MemcacheMetricStoreTest, self).setUp()

    self.state.target = targets.TaskTarget('myapp', 'mymodule', 'appengine', '')
    self.store.update_metric_index()

  def test_compare_and_set_failed(self):
    def fake_set(request, response):
      response.add_set_status(memcache_service_pb.MemcacheSetResponse.ERROR)

    memcache_stub = self.testbed.get_stub(testbed.MEMCACHE_SERVICE_NAME)
    memcache_stub._Dynamic_Set = fake_set

    self.store.set('foo', (('field', 'value'),), 42)

    self.assertIsNone(self.store.get('foo', (('field', 'value'),)))

  def test_report_module_versions(self):
    self.store.report_module_versions = True
    all_metrics = list(self.store.get_all())
    self.assertEqual(1, len(all_metrics))
    self.assertEqual('default', all_metrics[0][0].job_name)
    self.assertEqual('appengine/default_version', all_metrics[0][1].name)
    self.assertEqual({(): '1'}, all_metrics[0][3])

  def test_rejects_set_magical_metrics(self):
    with self.assertRaises(errors.MonitoringError):
      self.store.set('appengine/default_version', ((),), 'blah')
