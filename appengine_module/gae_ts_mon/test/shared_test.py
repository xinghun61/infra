# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import gae_ts_mon

from infra_libs.ts_mon import shared
from testing_utils import testing


class SharedTest(testing.AppengineTestCase):
  def setUp(self):
    super(SharedTest, self).setUp()
    shared.reset_for_unittest()

  def tearDown(self):
    shared.reset_for_unittest()
    self.assertEqual([], list(shared.global_metrics_callbacks))
    super(SharedTest, self).tearDown()

  def test_register_global_metrics(self):
    metric = gae_ts_mon.GaugeMetric('test', 'foo', None)
    shared.register_global_metrics([metric])
    self.assertEqual(['test'], list(shared.global_metrics))
    shared.register_global_metrics([metric])
    self.assertEqual(['test'], list(shared.global_metrics))
    shared.register_global_metrics([])
    self.assertEqual(['test'], list(shared.global_metrics))

  def test_register_global_metrics_callback(self):
    shared.register_global_metrics_callback('test', 'callback')
    self.assertEqual(['test'], list(shared.global_metrics_callbacks))
    shared.register_global_metrics_callback('nonexistent', None)
    self.assertEqual(['test'], list(shared.global_metrics_callbacks))
    shared.register_global_metrics_callback('test', None)
    self.assertEqual([], list(shared.global_metrics_callbacks))

  def test_get_instance_entity(self):
    entity = shared.get_instance_entity()
    # Save the modification, make sure it sticks.
    entity.task_num = 42
    entity.put()
    entity2 = shared.get_instance_entity()
    self.assertEqual(42, entity2.task_num)

    # Make sure it does not pollute the default namespace.
    self.assertIsNone(shared.Instance.get_by_id(entity.key.id()))
