# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import unittest
import json

from libs import time_util

from model import swarming_task_queue_request


class SwarmingTaskQueueRequestTest(unittest.TestCase):

  def testCreateDefault(self):
    request = swarming_task_queue_request.SwarmingTaskQueueRequest.Create()
    self.assertEqual(
        request.taskqueue_state,
        swarming_task_queue_request.SwarmingTaskQueueState.SCHEDULED)
    self.assertEqual(
        request.taskqueue_priority,
        swarming_task_queue_request.SwarmingTaskQueuePriority.FORCE)
    self.assertTrue(type(request.taskqueue_request_time) is datetime.datetime)
    self.assertEqual(request.taskqueue_dimensions, None)
    self.assertEqual(request.swarming_task_request, None)

  def testCreate(self):
    request = swarming_task_queue_request.SwarmingTaskQueueRequest.Create(
        taskqueue_state=swarming_task_queue_request.SwarmingTaskQueueState.
        READY,
        taskqueue_priority=swarming_task_queue_request.
        SwarmingTaskQueuePriority.FLAKE,
        taskqueue_request_time=datetime.datetime(2017, 1, 2),
        taskqueue_dimensions='dim',
        swarming_task_request='request')
    self.assertEqual(request.taskqueue_state,
                     swarming_task_queue_request.SwarmingTaskQueueState.READY)
    self.assertEqual(
        request.taskqueue_priority,
        swarming_task_queue_request.SwarmingTaskQueuePriority.FLAKE)
    self.assertEqual(request.taskqueue_request_time,
                     datetime.datetime(2017, 1, 2))
    self.assertEqual(request.taskqueue_dimensions, 'dim')
    self.assertEqual(request.swarming_task_request, 'request')
