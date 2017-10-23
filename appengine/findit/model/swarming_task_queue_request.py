# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json

from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from protorpc import messages

from libs import time_util


class SwarmingTaskQueuePriority():
  # Forced a rerun of a failure or flake.
  FORCE = 100
  FAILURE = 50
  FLAKE = 25
  # A request made through findit api.
  API_CALL = 10


class SwarmingTaskQueueState(messages.Enum):
  # Task has been sent to taskqueue, but not to swarming.
  SCHEDULED = 250

  # Task has been sent to swarming, but it hasn't completed.
  PENDING = 500

  # Task has been complete, but results haven't been requested.
  COMPLETED = 750

  # Task is complete, and results have been requested and recieved.
  READY = 1000


class SwarmingTaskQueueRequest(ndb.Model):
  # State of the request, see SwarmingTaskQueueState for details.
  taskqueue_state = msgprop.EnumProperty(SwarmingTaskQueueState, indexed=True)

  # Priority of the request, see SwarmingTaskQueuePriority for details.
  taskqueue_priority = ndb.IntegerProperty()

  # Timestamp to order things in the Taskqueue.
  taskqueue_request_time = ndb.DateTimeProperty()

  # Used to uniquely identify the machine this request needs.
  taskqueue_dimensions = ndb.StringProperty()

  # The actual request from waterfall/swarming_task_request's Serialize method.
  swarming_task_request = ndb.TextProperty()

  @staticmethod
  def Create(taskqueue_state=SwarmingTaskQueueState.SCHEDULED,
             taskqueue_priority=SwarmingTaskQueuePriority.FORCE,
             taskqueue_request_time=time_util.GetUTCNow(),
             taskqueue_dimensions=None,
             swarming_task_request=None):
    swarming_task_queue_request = SwarmingTaskQueueRequest()
    swarming_task_queue_request.taskqueue_state = taskqueue_state
    swarming_task_queue_request.taskqueue_priority = taskqueue_priority
    swarming_task_queue_request.taskqueue_request_time = taskqueue_request_time
    swarming_task_queue_request.taskqueue_dimensions = taskqueue_dimensions
    swarming_task_queue_request.swarming_task_request = swarming_task_request
    return swarming_task_queue_request
