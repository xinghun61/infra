#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility functions for Sheriff-o-matic."""

import calendar
import datetime
import hashlib
import json
import logging
import time
import urllib2
import webapp2

from datetime import datetime as dt
from google.appengine.api import users

from components import auth


def is_googler(): # pragma: no cover
  user = users.get_current_user()
  if user:
    email = user.email()
    return email.endswith('@google.com') and '+' not in email
  return False


def is_trooper_or_admin(): # pragma: no cover
  return (auth.is_group_member("mdb/chrome-troopers") or
      users.is_current_user_admin())


class DateTimeEncoder(json.JSONEncoder): # pragma: no cover
  def default(self, obj):  # pylint: disable=E0202
    if isinstance(obj, datetime.datetime):
      return calendar.timegm(obj.timetuple())
    # Let the base class default method raise the TypeError.
    return json.JSONEncoder.default(self, obj)


def convert_to_secs(duration_str): # pragma: no cover
  duration_str = duration_str.strip()
  if duration_str[-1] == 's':
    return int(duration_str[:-1])
  elif duration_str[-1] == 'm':
    return 60 * int(duration_str[:-1])
  elif duration_str[-1] == 'h':
    return 3600 * int(duration_str[:-1])
  elif duration_str[-1] == 'd':
    return 24 * 3600 * int(duration_str[:-1])
  elif duration_str[-1] == 'w':
    return 7 * 24 * 3600 * int(duration_str[:-1])
  else:
    raise Exception('Invalid duration_str ' + duration_str[-1])


def secs_ago(time_string, time_now=None): # pragma: no cover
  try:
    time_sent = dt.strptime(time_string, '%Y-%m-%d %H:%M:%S %Z')
  except ValueError:
    time_sent = dt.strptime(time_string, '%Y-%m-%d %H:%M:%S')
  time_now = time_now or int(dt.utcnow().strftime('%s'))
  latency = int(time_now) - int(time_sent.strftime('%s'))
  return latency


def hash_string(input_str): # pragma: no cover
  return hashlib.sha1(input_str).hexdigest()


def generate_json_dump(alerts, human_readable=True): # pragma: no cover
  if human_readable:
    return json.dumps(alerts, cls=DateTimeEncoder,
                              indent=2,
                              separators=(',', ': '))
  return json.dumps(alerts, cls=DateTimeEncoder,
                            indent=None,
                            separators=(',', ':'))
