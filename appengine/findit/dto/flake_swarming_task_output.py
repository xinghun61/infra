# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

from dto.swarming_task_error import SwarmingTaskError
from libs.structured_object import StructuredObject


class FlakeSwarmingTaskOutput(StructuredObject):
  # The timestamp that the task finished.
  completed_time = datetime

  # Any detected error in the task.
  error = SwarmingTaskError

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
