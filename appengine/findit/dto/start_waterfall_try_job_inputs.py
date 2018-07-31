# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dto.collect_swarming_task_results_outputs import (
    CollectSwarmingTaskResultsOutputs)
from libs.structured_object import StructuredObject
from services.parameters import BuildKey
from services.parameters import CompileHeuristicAnalysisOutput
from services.parameters import TestHeuristicAnalysisOutput


class StartTryJobInputs(StructuredObject):
  """This class is the base class for inputs of start try job pipelines."""
  build_key = BuildKey
  build_completed = bool
  force = bool


class StartTestTryJobInputs(StartTryJobInputs):
  """This class defines the input of StartTestTryJobPipeline."""
  heuristic_result = TestHeuristicAnalysisOutput
  consistent_failures = CollectSwarmingTaskResultsOutputs


class StartCompileTryJobInput(StartTryJobInputs):
  """This class defines the input of StartCompileTryJobPipeline."""
  heuristic_result = CompileHeuristicAnalysisOutput
