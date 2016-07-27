# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common import constants
from model import analysis_status
from model.base_swarming_task import BaseSwarmingTask
from model.base_build_model import BaseBuildModel

class FlakeSwarmingTask(BaseSwarmingTask, BaseBuildModel):
  """Represents a swarming task for a step w/candidate flaky tests.
  """

  @staticmethod
  def CreateSwarmingTaskId(
      master_name, builder_name, build_number,
      step_name, test_name):  # pragma: no cover
    return '%s/%s/%s/%s/%s' % (master_name, builder_name,
                               build_number, step_name, test_name)

  @staticmethod
  def _CreateKey(
       master_name, builder_name, build_number,
       step_name, test_name):  # pragma: no cover
    return ndb.Key('FlakeSwarmingTask',
                   FlakeSwarmingTask.CreateSwarmingTaskId(
                       master_name, builder_name, build_number,
                       step_name, test_name))

  @staticmethod
  def Create(
      master_name, builder_name, build_number,
      step_name, test_name):  # pragma: no cover
    return FlakeSwarmingTask(key=FlakeSwarmingTask._CreateKey(
      master_name, builder_name, build_number, step_name, test_name))

  @ndb.ComputedProperty
  def step_name(self):
    return self.key.pairs()[0][1].split('/')[3]

  @ndb.ComputedProperty
  def test_name(self):
    return self.key.pairs()[0][1].split('/')[4]


  @staticmethod
  def Get(
      master_name, builder_name, build_number,
      step_name, test_name):  # pragma: no cover
    return FlakeSwarmingTask._CreateKey(
        master_name, builder_name, build_number, step_name, test_name).get(
)
  # Number of runs the test passed.
  successes = ndb.IntegerProperty(default=0, indexed=False)
  # How many times the test was rerun.
  tries = ndb.IntegerProperty(default=0, indexed=False)
