# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from handlers.flake.detection import flake_detection_utils
from model import entity_util

_DEFAULT_OCCURRENCE_COUNT = 100


class ShowFlake(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    key = self.request.get('key')
    if not key:
      return self.CreateError(
          'Key is required to identify a flaky test.', return_code=404)

    flake = entity_util.GetEntityFromUrlsafeKey(key)
    if not flake:
      return self.CreateError(
          'Didn\'t find Flake for key %s.' % key, return_code=404)

    flake_dict = flake_detection_utils.GetFlakeInformation(
        flake, max_occurrence_count=_DEFAULT_OCCURRENCE_COUNT)

    data = {'flake_json': flake_dict}
    return {'template': 'flake/detection/show_flake.html', 'data': data}
