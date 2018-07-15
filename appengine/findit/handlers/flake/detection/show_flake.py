# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json

from google.appengine.ext import ndb

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission
from model import entity_util
from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import (
    CQFalseRejectionFlakeOccurrence)


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

    occurrences = CQFalseRejectionFlakeOccurrence.query(
        ancestor=flake.key).order(
            -CQFalseRejectionFlakeOccurrence.time_happened).fetch(100)

    flake_dict = flake.to_dict()
    flake_dict['occurrences'] = [
        occurrence.to_dict() for occurrence in occurrences
    ]

    if flake.flake_issue_key:
      flake_issue = flake.flake_issue_key.get()
      flake_dict['flake_issue'] = flake_issue.to_dict()

    data = {'flake_json': flake_dict}
    return {'template': 'flake/detection/show_flake.html', 'data': data}
