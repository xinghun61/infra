# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import os
import sys
import webapp2

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'third_party'))

from findit_api import findit_api
from google.appengine.api import taskqueue

from common.request_entity import Request, RequestManager, Status


# The number of tasks we can schedule using the Findit API per day as
# specified by @lijeffrey
SWARMING_TASK_LIMIT = 120
# Number of times we want to schedule new tasks
MAX_TIMES_SCHEDULED = 5


def _get_response(request, api):
  """ Return the findit_api response for a request """
  return (api.checkFlakeSwarmingTask(request.master_name,
                                     request.builder_name,
                                     request.build_number,
                                     request.step_name,
                                     request.test_name))

def _update_pending_queue(manager, api):
  """ Updates the response for all requests that have already been completed

  Function to take requests that have already been completed by Findit off
  of the pending queue. If the request has been completed, the response is
  added and the request is moved to completed.
  """
  still_pending = []
  for request_key in manager.pending:
    request = request_key.get()
    response = _get_response(request, api)

    # Completed must be in the response and set to true because if the task
    # fails, the field will be false.
    if ('completed' in response and response['completed']):
      request.swarming_response = response
      request.status = Status.COMPLETED
      manager.add_request(request)
    else:
      still_pending.append(request.key)

  manager.pending = still_pending

def _schedule_test_reruns(manager, api):
  """ Schedules as many reruns as possible

  Function that goes over pending list and schedules reruns until the swarming
  task limit is met. If an entitiy is not successfully scheduled, it is dropped
  """
  while (
      manager.num_scheduled < SWARMING_TASK_LIMIT and len(manager.pending) > 0):
    request = manager.pending.pop(0).get()
    response = api.triggerFlakeSwarmingTask(request.master_name,
                                            request.builder_name,
                                            request.build_number,
                                            request.step_name,
                                            request.test_name)
    # When 'queued' is missing or False, it means that the request
    # is not supported or an error occured on the Findit side.
    if ('queued' in response and response['queued']):
      manager.num_scheduled += 1
      request.status = Status.RUNNING
      manager.add_request(request)
    else:
      request.key.delete()

def _update_running_queue(manager, api):
  """ Check running entities status, update if completed successfully

  Iterates over the currently running tasks and checks if they are completed.
  Tasks that are completed are updated and added to completed. If the task did
  not complete successfully and is not still waiting, it is discarded
  """
  still_running = []
  for request_key in manager.running:
    request = request_key.get()
    response = _get_response(request, api)

    if ('completed' in response and response['completed']):
      request.swarming_response = response
      request.status = Status.COMPLETED
      manager.add_request(request)
    elif ('queued' in response and response['queued']):
      still_running.append(request.key)
    else:
      request.key.delete()

  manager.running = still_running

class RerunRequestHandler(webapp2.RequestHandler):
  def get(self):
    manager = RequestManager.load()
    api = findit_api.FindItAPI()
    time_scheduled = datetime.datetime.strptime(
        self.request.get('time_scheduled', str(datetime.datetime.utcnow())),
        '%Y-%m-%d %H:%M:%S')
    num_taskqueue_runs = int(self.request.get('num_taskqueue_runs', '1'))

    # First time run, get all already completed entities and schedule new ones.
    # Otherwise, schedule new tasks if a day has passed and update running tasks
    if num_taskqueue_runs == 1:
      _update_pending_queue(manager, api)
      _schedule_test_reruns(manager, api)
    else:
      _update_running_queue(manager, api)
      if (datetime.datetime.utcnow() - time_scheduled
          >= datetime.timedelta(hours=23, minutes=50) and
          num_taskqueue_runs < MAX_TIMES_SCHEDULED):
        manager.num_scheduled = 0
        _schedule_test_reruns(manager, api)

    # Run again in a day. Do not run again if there is nothing more to schedule
    # and everything has been completed, or the maximum has been reached
    if (num_taskqueue_runs < MAX_TIMES_SCHEDULED or
        (len(manager.pending) == 0 and len(manager.running) == 0)):
      taskqueue.add(url='/handlers/rerun-request-handler',
                    countdown=86400,  # 24h
                    params={
                        'time_scheduled': datetime.datetime.utcnow(),
                        'num_taskqueue_runs': num_taskqueue_runs + 1},)
    manager.save()
