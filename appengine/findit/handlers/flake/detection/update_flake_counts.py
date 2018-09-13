# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import taskqueue

from common import constants
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from services.flake_detection import update_flake_counts_service


class UpdateFlakeCountsCron(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    # Runs the tasks in the same queue as flake detection tasks to make sure
    # data consistency: at most one task can be executed any time in that queue.
    taskqueue.add(
        method='GET',
        queue_name=constants.FLAKE_DETECTION_QUEUE,
        target=constants.FLAKE_DETECTION_BACKEND,
        url='/flake/detection/task/update-flake-counts')
    return {'return_code': 200}


class UpdateFlakeCountsTask(BaseHandler):
  """Updates flakes periodically on statistical fields.

  Currently we only have weekly counts to update. Later we may also maintain
  daily or monthly counts.
  """
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    update_flake_counts_service.UpdateFlakeCounts()
