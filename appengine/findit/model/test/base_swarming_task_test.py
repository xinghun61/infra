# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from model.wf_swarming_task import WfSwarmingTask


class BaseSwarmingTaskTest(unittest.TestCase):

  def testReset(self):
    task = WfSwarmingTask.Create('m', 'b', 121, 'browser_tests')
    task.task_id = 'task_id'
    task.Reset()
    self.assertIsNone(task.task_id)