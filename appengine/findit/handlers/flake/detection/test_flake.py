# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json

from google.appengine.ext import ndb

from gae_libs.handlers.base_handler import BaseHandler
from gae_libs.handlers.base_handler import Permission

from model import entity_util
from model.flake.detection.flake import Flake
from model.flake.detection.flake_occurrence import FlakeOccurrence, FlakeType


class TestFlake(BaseHandler):
  PERMISSION_LEVEL = Permission.ANYONE

  def HandleGet(self):
    key = self.request.get('key')
    if not key:
      return self.CreateError('Key is a required parameter.')

    flake = entity_util.GetEntityFromUrlsafeKey(key)
    if not flake:
      return self.CreateError('Didn\'t find Flake for key %s.' % key)

    flake_occurrences = FlakeOccurrence.query(ancestor=flake.key).order(
        -FlakeOccurrence.time_reported).fetch(100)

    flake_dict = flake.to_dict()
    flake_dict['occurrences'] = [
        occurrence.to_dict() for occurrence in flake_occurrences
    ]

    data = {'flake_json': flake_dict}

    return {'template': 'flake/detection/test_flake.html', 'data': data}
