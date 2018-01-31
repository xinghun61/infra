# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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
  # Any detected error in the task.
  error = SwarmingTaskError

  # The number of iterations ran.
  iterations = int

  # The number of iterations that the test passed.
  pass_count = int


class RunFlakeSwarmingTaskPipeline(AsynchronousPipeline):

  input_type = RunFlakeSwarmingTaskInput
  output_type = RunFlakeSwarmingTaskOutput

  def RunImpl(self, parameters):  # pragma: no cover
    # TODO(crbug.com/799569): Implement RunFlakeSwarmingTaskPipeline.
    pass
