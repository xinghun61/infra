# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel
from model.base_swarming_task import BaseSwarmingTask


class WfSwarmingTask(BaseBuildModel, BaseSwarmingTask):
  """Represents a swarming task for a failed step.

  'Wf' is short for waterfall.
  """

  @property
  def classified_tests(self):
    """Classification of tests into lists of reliable and flaky tests.

    example format would be:
    {
        'flaky_tests': ['test1', 'test2', ...],
        'reliable_tests': ['test3', ...],
        'unknown_tests': ['test4', ...]
    }
    """
    classified_tests = defaultdict(list)
    for test_name, test_statuses in self.tests_statuses.iteritems():
      if test_statuses.get('SUCCESS'):  # Test passed for some runs, flaky.
        classified_tests['flaky_tests'].append(test_name)
      elif test_statuses.get('UNKNOWN'):
        classified_tests['unknown_tests'].append(test_name)
      else:
        # Here we consider a 'non-flaky' test to be 'reliable'.
        # If the test is 'SKIPPED', there should be failure in its dependency,
        # consider it to be failed as well.
        # TODO(chanli): Check more test statuses.
        classified_tests['reliable_tests'].append(test_name)
    return classified_tests

  @property
  def reliable_tests(self):
    return self.classified_tests.get('reliable_tests', [])

  @property
  def flaky_tests(self):
    return self.classified_tests.get('flaky_tests', [])

  @ndb.ComputedProperty
  def step_name(self):
    return self.key.pairs()[1][1]

  @staticmethod
  def _CreateKey(master_name, builder_name, build_number,
                 step_name):  # pragma: no cover
    build_id = BaseBuildModel.CreateBuildId(master_name, builder_name,
                                            build_number)
    return ndb.Key('WfBuild', build_id, 'WfSwarmingTask', step_name)

  @staticmethod
  def Create(master_name, builder_name, build_number,
             step_name):  # pragma: no cover
    task = WfSwarmingTask(key=WfSwarmingTask._CreateKey(
        master_name, builder_name, build_number, step_name))
    task.parameters = task.parameters or {}
    task.tests_statuses = task.tests_statuses or {}
    return task

  @staticmethod
  def Get(master_name, builder_name, build_number,
          step_name):  # pragma: no cover
    return WfSwarmingTask._CreateKey(master_name, builder_name, build_number,
                                     step_name).get()
