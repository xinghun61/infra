# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from dto.swarming_task_error import SwarmingTaskError
from gae_libs.pipelines import AsynchronousPipeline
from libs.structured_object import StructuredObject


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


class RunFlakeSwarmingTaskPipeline(AsynchronousPipeline):

  input_type = RunFlakeSwarmingTaskInput
  output_type = RunFlakeSwarmingTaskOutput

  def RunImpl(self, parameters):  # pragma: no cover
    # TODO(crbug.com/799569): Implement RunFlakeSwarmingTaskPipeline.
    pass
