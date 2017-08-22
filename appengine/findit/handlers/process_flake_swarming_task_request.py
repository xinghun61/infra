# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pickle

from common import constants
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from waterfall.flake import trigger_flake_swarming_task_service_pipeline


class ProcessFlakeSwarmingTaskRequest(BaseHandler):
  """Processes a request to trigger a flake swarming task on demand."""

  PERMISSION_LEVEL = Permission.APP_SELF

  def HandlePost(self):
    (master_name, builder_name, build_number, step_name, test_name,
     iterations_to_rerun, user_email) = pickle.loads(self.request.body)

    trigger_flake_swarming_task_service_pipeline.ScheduleFlakeSwarmingTask(
        master_name,
        builder_name,
        build_number,
        step_name,
        test_name,
        iterations_to_rerun,
        user_email,
        queue_name=constants.WATERFALL_FLAKE_SWARMING_TASK_REQUEST_QUEUE)
