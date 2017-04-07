# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64

from google.appengine.ext import ndb

from libs import analysis_status
from model.base_build_model import BaseBuildModel
from model.base_swarming_task import BaseSwarmingTask


class FlakeSwarmingTaskData(ndb.Model):
  task_id = ndb.StringProperty(indexed=False)
  status = ndb.IntegerProperty(indexed=False)
  error = ndb.JsonProperty(indexed=False)
  created_time = ndb.DateTimeProperty(indexed=False)
  started_time = ndb.DateTimeProperty(indexed=False)
  completed_time = ndb.DateTimeProperty(indexed=False)
  cache_hit = ndb.IntegerProperty(indexed=False)
  number_of_iterations = ndb.IntegerProperty(indexed=False)
  number_of_passes = ndb.IntegerProperty(indexed=False)


class FlakeSwarmingTask(BaseSwarmingTask, BaseBuildModel):
  """Represents a swarming task for a step w/candidate flaky tests.
  """

  @staticmethod
  def _CreateSwarmingTaskId(master_name, builder_name, build_number,
                            step_name, test_name):  # pragma: no cover
    encoded_test_name = base64.urlsafe_b64encode(test_name)
    return '%s/%s/%s/%s/%s' % (master_name, builder_name,
                               build_number, step_name, encoded_test_name)

  @staticmethod
  def _CreateKey(master_name, builder_name, build_number,
                 step_name, test_name):  # pragma: no cover
    return ndb.Key('FlakeSwarmingTask',
                   FlakeSwarmingTask._CreateSwarmingTaskId(
                       master_name, builder_name, build_number,
                       step_name, test_name))

  @staticmethod
  def Create(master_name, builder_name, build_number,
             step_name, test_name):  # pragma: no cover
    return FlakeSwarmingTask(key=FlakeSwarmingTask._CreateKey(
        master_name, builder_name, build_number, step_name, test_name))

  @ndb.ComputedProperty
  def step_name(self):
    return self.key.pairs()[0][1].split('/')[3]

  @ndb.ComputedProperty
  def test_name(self):
    return base64.urlsafe_b64decode(self.key.pairs()[0][1].split('/')[4])

  @staticmethod
  def Get(master_name, builder_name, build_number,
          step_name, test_name):  # pragma: no cover
    return FlakeSwarmingTask._CreateKey(
        master_name, builder_name, build_number, step_name, test_name).get()

  def GetFlakeSwarmingTaskData(self):
    flake_swarming_task_data = FlakeSwarmingTaskData()
    flake_swarming_task_data.task_id = self.task_id
    flake_swarming_task_data.created_time = self.created_time
    flake_swarming_task_data.started_time = self.started_time
    flake_swarming_task_data.completed_time = self.completed_time
    flake_swarming_task_data.error = self.error
    flake_swarming_task_data.number_of_iterations = self.tries
    flake_swarming_task_data.number_of_passes = self.successes
    flake_swarming_task_data.status = self.status
    # TODO(lijeffrey): Determine cache_hit.
    return flake_swarming_task_data

  # Number of runs the test passed.
  successes = ndb.IntegerProperty(default=0, indexed=False)
  # How many times the test was rerun.
  tries = ndb.IntegerProperty(default=0, indexed=False)

  def Reset(self):
    """Resets the task as if it's a new task."""
    self.task_id = None
    self.tests_statuses = None
    self.status = analysis_status.PENDING
    self.error = None
    self.created_time = None
    self.started_time = None
    self.completed_time = None
    self.parameters = {}
    self.successes = None
    self.tries = None
