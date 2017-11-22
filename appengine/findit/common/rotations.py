# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities to get the sheriff(s) on duty"""

import json

from common.findit_http_client import FinditHttpClient
from libs import time_util
from model.wf_config import FinditConfig

_ROTATIONS_URL = (
    'https://build.chromium.org/deprecated/chromium/all_rotations.js')

_HTTP_CLIENT = FinditHttpClient()


def get_rotation_url():
  return FinditConfig().Get().action_settings.get('rotations_url',
                                                  _ROTATIONS_URL)


def get_all_rotations():
  status_code, content = _HTTP_CLIENT.Get(get_rotation_url())
  if status_code == 200:
    content = json.loads(content)
    today = time_util.GetPSTNow().date().isoformat()
    calendars = content['calendar']
    rotations = content['rotations']
    for calendar in calendars:
      if calendar['date'] == today:
        sheriffs = [['%s@google.com' % p.split('@')[0] for p in q]
                    for q in calendar['participants']]
        return dict(zip(rotations, sheriffs))
    raise Exception('Today\'s date (%s) is not listed in the rotations '
                    'calendar at %s' % (today, _ROTATIONS_URL))
  else:
    raise Exception('Could not retrieve sheriff list from %s, got code %d' %
                    (_ROTATIONS_URL, status_code))


def current_sheriffs(rotation_name='chrome'):
  return get_all_rotations().get(rotation_name, [])
