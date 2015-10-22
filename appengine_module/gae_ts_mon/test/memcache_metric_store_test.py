# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import gae_ts_mon
import mock

from google.appengine.ext import testbed
from google.appengine.api.memcache import memcache_service_pb

from infra_libs.ts_mon import memcache_metric_store
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
