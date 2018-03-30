# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs.structured_object import StructuredObject
from libs.structured_object import TypedDict


class ConsistentTestFailures(TypedDict):
  _value_type = list


class CollectSwarmingTaskResultsOutputs(StructuredObject):
  """This class defines the output of collect_swarming_task_results_pipeline."""
  consistent_failures = ConsistentTestFailures