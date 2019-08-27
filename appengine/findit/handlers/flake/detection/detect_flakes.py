# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import urllib2

from google.appengine.api import taskqueue

from common import constants
from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from model.flake.flake_type import DESCRIPTION_TO_FLAKE_TYPE
from model.flake.flake_type import FlakeType
from model.flake.flake_type import FLAKE_TYPE_DESCRIPTIONS
from services.flake_detection import detect_flake_occurrences
from services.flake_detection.detect_flake_occurrences import (
    DetectFlakesFromFlakyCQBuildParam)

_TOTAL_FLAKE_TYPES = [
    FlakeType.CQ_FALSE_REJECTION,
    FlakeType.RETRY_WITH_PATCH,
    FlakeType.CQ_HIDDEN_FLAKE,
]

_NON_HIDDEN_FLAKE_TYPES = [
    FlakeType.CQ_FALSE_REJECTION,
    FlakeType.RETRY_WITH_PATCH,
]


class DetectFlakesCronJob(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    # Cron jobs run independently of each other. Therefore, there is no
    # guarantee that they will run either sequentially or simultaneously.

    for flake_type in _TOTAL_FLAKE_TYPES:
      # Running flake detection tasks concurrently doesn't bring much benefits,
      # so use task queue to enforce that at most one detection task can be
      # executed at any time to avoid any potential race condition.
      taskqueue.add(
          method='GET',
          queue_name=constants.FLAKE_DETECTION_QUEUE,
          target=constants.FLAKE_DETECTION_BACKEND,
          url='/flake/detection/task/detect-flakes?flake_type={}'.format(
              urllib2.quote(FLAKE_TYPE_DESCRIPTIONS[flake_type])))
    return {'return_code': 200}


class FlakeDetection(BaseHandler):
  PERMISSION_LEVEL = Permission.APP_SELF

  def HandleGet(self):
    flake_type_desc = self.request.get('flake_type')
    if not flake_type_desc or not DESCRIPTION_TO_FLAKE_TYPE.get(
        flake_type_desc):
      return self.CreateError(
          'Invalid flake type for flake detection.', return_code=404)

    flake_type = DESCRIPTION_TO_FLAKE_TYPE[flake_type_desc]
    if flake_type in _NON_HIDDEN_FLAKE_TYPES:
      detect_flake_occurrences.QueryAndStoreNonHiddenFlakes(flake_type)
    else:
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
