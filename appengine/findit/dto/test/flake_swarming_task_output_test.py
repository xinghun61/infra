# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from dto.flake_swarming_task_output import FlakeSwarmingTaskOutput
from gae_libs.testcase import TestCase


class FlakeSwarmingTaskOutputTest(TestCase):

  def testGetElapsedSecondsNoStartEndTimes(self):
    task_output = FlakeSwarmingTaskOutput(
        completed_time=None,
        error=None,
        iterations=50,
        pass_count=25,
        started_time=None,
        task_id='task_id')
    self.assertIsNone(task_output.GetElapsedSeconds())

  def testGetElapsedSeconds(self):
    task_output = FlakeSwarmingTaskOutput(
        completed_time=datetime(2018, 2, 21, 0, 1, 0),
        error=None,
        iterations=50,
        pass_count=25,
        started_time=datetime(2018, 2, 21, 0, 0, 0),
        task_id='task_id')
    self.assertEqual(60, task_output.GetElapsedSeconds())
