from google.appengine.ext import ndb

import logging

from waterfall.trigger_base_swarming_task_pipeline import(
    TriggerBaseSwarmingTaskPipeline)
from model.flake.flake_swarming_task import FlakeSwarmingTask
class TriggerFlakeSwarmingTaskPipeline(TriggerBaseSwarmingTaskPipeline):
  """A pipeline to check if selected tests of a step are flaky.

  This pipeline only supports test steps that run on Swarming and support the
  gtest filter.
  """
  #pylint: disable=arguments-differ
  def _GetSwarmingTask(self,master_name, builder_name, build_number,
                       step_name, test_name):
    # Get the appropriate kind of Swarming Task (Flake).
    swarming_task = FlakeSwarmingTask.Get(
        master_name, builder_name, build_number, step_name, test_name)
    return swarming_task

  #pylint: disable=arguments-differ
  def _CreateSwarmingTask(self, master_name, builder_name, build_number,
                          step_name, test_name):
    # Create the appropriate kind of Swarming Task (Flake).
    swarming_task = FlakeSwarmingTask.Create(
        master_name, builder_name, build_number, step_name, test_name)
    return swarming_task

  def _GetIterationsToRerun(self):
    # How many times we want to run the swarming rerun?
    return 10

  def _GetArgs(self, master_name, builder_name, build_number, step_name, tests):
    test_name = tests[0] #only one test per pipeline
    return (master_name, builder_name, build_number, step_name, test_name)
