# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel
from model import analysis_status


class WfSwarmingTask(BaseBuildModel):
  """Represents a swarming task for a failed step.

  'Wf' is short for waterfall.
  """
  # The id of the Swarming task scheduled or running on Swarming Server.
  task_id = ndb.StringProperty(indexed=False)

  # A dict to keep track of running information for each test:
  # number of total runs, number of each status (such as 'SUCCESS' or 'FAILED')
  tests_statuses = ndb.JsonProperty(default={}, indexed=False, compressed=True)

  # The status of the swarming task.
  status = ndb.IntegerProperty(
      default=analysis_status.PENDING, indexed=False)

  # The revision of the failed build.
  build_revision = ndb.StringProperty(indexed=False)

  # Time when the task is created.
  created_time = ndb.DateTimeProperty(indexed=True)
  # Time when the task is started.
  started_time = ndb.DateTimeProperty(indexed=False)
  # Time when the task is completed.
  completed_time = ndb.DateTimeProperty(indexed=False)

  # parameters need to be stored and analyzed later.
  parameters = ndb.JsonProperty(default={}, indexed=False, compressed=True)

  @property
  def classified_tests(self):
    """Classification of tests into lists of reliable and flaky tests.

    example format would be:
    {
        'flaky_tests': ['test1', 'test2', ...],
        'reliable_tests': ['test3', ...]
    }
    """
    classified_tests = defaultdict(list)
    for test_name, test_statuses in self.tests_statuses.iteritems():
      if test_statuses.get('SUCCESS'):  # Test passed for some runs, flaky.
        classified_tests['flaky_tests'].append(test_name)
      else:
        # Here we consider a 'non-flaky' test to be 'reliable'.
        # TODO(chanli): Check more test statuses.
        classified_tests['reliable_tests'].append(test_name)
    return classified_tests

  @staticmethod
  def _CreateKey(
      master_name, builder_name, build_number, step_name):  # pragma: no cover
    build_id = BaseBuildModel.CreateBuildId(
        master_name, builder_name, build_number)
    return ndb.Key('WfBuild', build_id, 'WfSwarmingTask', step_name)

  @staticmethod
  def Create(
      master_name, builder_name, build_number, step_name):  # pragma: no cover
    return WfSwarmingTask(
        key=WfSwarmingTask._CreateKey(
            master_name, builder_name, build_number, step_name))

  @staticmethod
  def Get(
      master_name, builder_name, build_number, step_name):  # pragma: no cover
    return WfSwarmingTask._CreateKey(
        master_name, builder_name, build_number, step_name).get()
