# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from google.appengine.api import taskqueue

from common import constants
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from model.flake.flake_type import FlakeType
from services.flake_detection import detect_flake_occurrences
from services.flake_detection.detect_flake_occurrences import (
    DetectFlakesFromFlakyCQBuildParam)


class DetectFlakesCronJob(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    # Cron jobs run independently of each other. Therefore, there is no
    # guarantee that they will run either sequentially or simultaneously.
    #
    # Running flake detection tasks concurrently doesn't bring much benefits, so
    # use task queue to enforce that at most one detection task can be executed
    # at any time to avoid any potential race condition.
    taskqueue.add(
        method='GET',
        queue_name=constants.FLAKE_DETECTION_QUEUE,
        target=constants.FLAKE_DETECTION_BACKEND,
        url='/flake/detection/task/detect-flakes')
    return {'return_code': 200}


class FlakeDetection(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    detect_flake_occurrences.QueryAndStoreFlakes(FlakeType.CQ_FALSE_REJECTION)
    detect_flake_occurrences.QueryAndStoreFlakes(FlakeType.RETRY_WITH_PATCH)
    detect_flake_occurrences.QueryAndStoreHiddenFlakes()
    return {'return_code': 200}


class DetectFlakesFromFlakyCQBuild(BaseHandler):
  """Detects a type of flakes from a flaky CQ build.

  Supported flake types:
    - FlakeType.CQ_FALSE_REJECTION
    - FlakeType.RETRY_WITH_PATCH

  """
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandlePost(self):
    params = json.loads(self.request.body)
    detect_flake_occurrences.ProcessBuildForFlakes(
        DetectFlakesFromFlakyCQBuildParam.FromSerializable(params))
