# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model.flake.flake_swarming_task import FlakeSwarmingTask


class FlakeSwarmingTaskTest(unittest.TestCase):

  def testStepTestName(self):
    task = FlakeSwarmingTask.Create('m', 'b', 121, 'browser_tests', 'test1')
    self.assertEqual('browser_tests', task.step_name)
    self.assertEqual('test1', task.test_name)
