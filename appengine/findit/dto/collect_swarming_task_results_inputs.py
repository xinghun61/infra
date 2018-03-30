# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs.structured_object import StructuredObject
from services.parameters import BuildKey


class CollectSwarmingTaskResultsInputs(StructuredObject):
  """This class defines the input of collect_swarming_task_results_pipeline."""
  build_key = BuildKey
  build_completed = bool