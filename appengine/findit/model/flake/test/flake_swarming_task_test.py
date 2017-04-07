# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

import unittest

from libs import analysis_status
from model.flake.flake_swarming_task import FlakeSwarmingTask


class FlakeSwarmingTaskTest(unittest.TestCase):

  def testStepTestName(self):
    task = FlakeSwarmingTask.Create('m', 'b', 121, 'browser_tests', 'test1')
    self.assertEqual('browser_tests', task.step_name)
    self.assertEqual('test1', task.test_name)

  def testGetFlakeSwarmingTaskData(self):
    task_id = 'task_1'
    master_name = 'm'
    builder_name = 'b'
    build_number = 121
    step_name = 'browser_tests'
    test_name = 'test1'
    created_time = datetime(2016, 9, 26, 0, 0, 0, 0)
    started_time = datetime(2016, 9, 26, 0, 1, 0, 0)
    completed_time = datetime(2016, 9, 26, 0, 2, 0, 0)
    number_of_iterations = 100
    number_of_passes = 100

    task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    task.task_id = task_id
    task.created_time = created_time
    task.started_time = started_time
    task.completed_time = completed_time
    task.tries = number_of_iterations
    task.successes = number_of_passes
    task.error = None
    task.status = analysis_status.COMPLETED

    data = task.GetFlakeSwarmingTaskData()

    self.assertEqual(task_id, data.task_id)
    self.assertEqual(created_time, data.created_time)
    self.assertEqual(started_time, data.started_time)
    self.assertEqual(completed_time, data.completed_time)
    self.assertEqual(number_of_iterations, data.number_of_iterations)
    self.assertEqual(number_of_passes, data.number_of_passes)
    self.assertEqual(analysis_status.COMPLETED, data.status)
    self.assertIsNone(data.error)

  def testReset(self):
    task = FlakeSwarmingTask.Create('m', 'b', 121, 'browser_tests', 'test1')
    task.task_id = 'task_id'
    task.Reset()
    self.assertIsNone(task.task_id)
