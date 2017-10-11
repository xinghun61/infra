# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities to get the sheriff(s) on duty"""

import json

from common.findit_http_client import FinditHttpClient
from libs import time_util

ROTATIONS_URL = 'https://build.chromium.org/p/chromium/all_rotations.js'

HTTP_CLIENT = FinditHttpClient()


def get_all_rotations():
  status_code, content = HTTP_CLIENT.Get(ROTATIONS_URL)
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
                    'calendar at %s' % (today, ROTATIONS_URL))
  else:
    raise Exception('Could not retrieve sheriff list from %s, got code %d' %
                    (ROTATIONS_URL, status_code))


def current_sheriffs(rotation_name='chrome'):
  return get_all_rotations().get(rotation_name, [])
