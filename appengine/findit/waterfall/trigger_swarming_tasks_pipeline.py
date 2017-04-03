# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from google.appengine.ext import ndb

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import BasePipeline
from model.wf_analysis import WfAnalysis
from waterfall.trigger_swarming_task_pipeline import TriggerSwarmingTaskPipeline


@ndb.transactional
def _GetStepsThatNeedToTriggerSwarmingTasks(
    master_name, builder_name, build_number, failure_info):
  """Gets first time failed steps and tests which haven't triggered
     swarming tasks.
  """
  result_steps = defaultdict(list)
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)

  if not analysis:
    return result_steps
  failure_result_map = analysis.failure_result_map

  # A dict to store all the first time failed steps and/ or tests which
  # have not triggered a swarming task yet.
  for failed_step, step_failure in failure_info['failed_steps'].iteritems():
    if failure_result_map.get(failed_step):
      # The step has been processed.
      continue

    if not step_failure.get('tests'):  # Not a swarming gtest.
      continue

    failure_result_map[failed_step] = {}
    for failed_test, test_failure in step_failure['tests'].iteritems():
      task_key = '%s/%s/%s' % (
        master_name, builder_name, test_failure['first_failure'])
      failure_result_map[failed_step][failed_test] = task_key

      if test_failure['first_failure'] == test_failure['current_failure']:
        # First time failure, add to result_steps.
        result_steps[failed_step].append(test_failure['base_test_name'])
  analysis.put()
  return result_steps


class TriggerSwarmingTasksPipeline(BasePipeline):
  """Root Pipeline to trigger swarming tasks."""

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, failure_info):
    if (not failure_info or not failure_info['failed_steps'] or
        not failure_info['failure_type'] == failure_type.TEST):
      return

    steps = _GetStepsThatNeedToTriggerSwarmingTasks(
        master_name, builder_name, build_number, failure_info)
    for step_name, base_tests in steps.iteritems():
      yield TriggerSwarmingTaskPipeline(
          master_name, builder_name, build_number, step_name, base_tests)
