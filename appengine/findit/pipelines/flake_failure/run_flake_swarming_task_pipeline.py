# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from google.appengine.ext import ndb

from dto.swarming_task_error import SwarmingTaskError
from gae_libs.pipelines import GeneratorPipeline
from gae_libs.pipelines import pipeline
from gae_libs.pipelines import SynchronousPipeline
from libs.structured_object import StructuredObject
from model.flake.flake_swarming_task import FlakeSwarmingTask
from services import step_util
from waterfall import build_util
from waterfall.process_flake_swarming_task_result_pipeline import (
    ProcessFlakeSwarmingTaskResultPipeline)
from waterfall.trigger_flake_swarming_task_pipeline import (
    TriggerFlakeSwarmingTaskPipeline)


class RunFlakeSwarmingTaskInput(StructuredObject):
  # The urlsafe key of the MasterFlakeAnalysis in progress.
  analysis_urlsafe_key = basestring

  # The commit position to run the flake swarming task against.
  commit_position = int

  # The isolate sha pointing to the binaries to test.
  isolate_sha = basestring

  # The number of iterations to run.
  iterations = int

  # The number of seconds the task must complete in
  timeout_seconds = int


class RunFlakeSwarmingTaskOutput(StructuredObject):
  # The timestamp that the task finished.
  completed_time = datetime

  # Any detected error in the task.
  error = SwarmingTaskError

  # Whether or not the task has valid artifacts.
  has_valid_artifact = bool

  # The number of iterations ran.
  iterations = int

  # The number of iterations that the test passed.
  pass_count = int

  # The timestamp that the task started.
  started_time = datetime

  # The id of the task that was run.
  task_id = basestring

  def GetElapsedSeconds(self):
    """Determines the integer number of seconds the task took to complete."""
    if not self.completed_time or not self.started_time:
      return None
    return int((self.completed_time - self.started_time).total_seconds())


class CollectFlakeSwarmingTaskOutputInput(StructuredObject):
  # TODO(crbug.com/799569): Remove once asynchronous pipeline is in place.
  master_name = basestring
  builder_name = basestring
  reference_build_number = int
  step_name = basestring
  test_name = basestring


class CollectFlakeSwarmingTaskOutputPipeline(SynchronousPipeline):
  # TODO(crbug.com/799569): Remove temporary pipeline once asynchronous one
  # is in place.

  input_type = CollectFlakeSwarmingTaskOutputInput
  output_type = RunFlakeSwarmingTaskOutput

  def RunImpl(self, parameters):

    flake_swarming_task = FlakeSwarmingTask.Get(
        parameters.master_name, parameters.builder_name,
        parameters.reference_build_number, parameters.step_name,
        parameters.test_name)

    assert flake_swarming_task

    error = flake_swarming_task.error or None
    if error:
      error = SwarmingTaskError.FromSerializable(error)

    return RunFlakeSwarmingTaskOutput(
        completed_time=flake_swarming_task.completed_time,
        error=error,
        has_valid_artifact=flake_swarming_task.has_valid_artifact,
        iterations=flake_swarming_task.tries,
        pass_count=flake_swarming_task.successes,
        started_time=flake_swarming_task.started_time,
        task_id=flake_swarming_task.task_id)


class RunFlakeSwarmingTaskPipeline(GeneratorPipeline):

  input_type = RunFlakeSwarmingTaskInput
  output_type = RunFlakeSwarmingTaskOutput

  def RunImpl(self, parameters):
    # TODO(crbug.com/799569): Implement RunFlakeSwarmingTaskPipeline using
    # new asynchronous pipeline once ready. Until then, use old pipelines to
    # enable testing of new Flake Analyzer pipelines.
    analysis_urlsafe_key = parameters.analysis_urlsafe_key
    analysis = ndb.Key(urlsafe=analysis_urlsafe_key).get()
    assert analysis

    master_name = analysis.master_name
    builder_name = analysis.builder_name
    _, upper_bound_build = step_util.GetValidBoundingBuildsForStep(
        master_name, builder_name, analysis.step_name, None, None,
        parameters.commit_position)
    build_number = upper_bound_build.build_number

    with pipeline.InOrder():
      task_id = yield TriggerFlakeSwarmingTaskPipeline(
          master_name,
          builder_name,
          build_number,
          analysis.step_name, [analysis.test_name],
          parameters.isolate_sha,
          iterations_to_rerun=parameters.iterations,
          hard_timeout_seconds=parameters.timeout_seconds,
          force=True)
      yield ProcessFlakeSwarmingTaskResultPipeline(
          master_name, builder_name, build_number, analysis.step_name, task_id,
          analysis.build_number, analysis.test_name, analysis.version_number)
      collect_result_input = self.CreateInputObjectInstance(
          CollectFlakeSwarmingTaskOutputInput,
          master_name=master_name,
          builder_name=builder_name,
          reference_build_number=build_number,
          step_name=analysis.step_name,
          test_name=analysis.test_name)
      yield CollectFlakeSwarmingTaskOutputPipeline(collect_result_input)
