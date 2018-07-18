# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import gae_ts_mon

from test_support import test_case

from infra_libs.ts_mon import shared


class SharedTest(test_case.TestCase):
  def test_get_instance_entity(self):
    entity = shared.get_instance_entity()
    # Save the modification, make sure it sticks.
    entity.task_num = 42
    entity.put()
    entity2 = shared.get_instance_entity()
    self.assertEqual(42, entity2.task_num)

    # Make sure it does not pollute the default namespace.
    self.assertIsNone(shared.Instance.get_by_id(entity.key.id()))
