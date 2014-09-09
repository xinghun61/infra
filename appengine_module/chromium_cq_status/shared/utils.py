# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import hashlib
import json

from google.appengine.api import users

from appengine_module.chromium_cq_status.shared.config import VALID_EMAIL_RE

compressed_separators = (',', ':')

def cronjob(cronjob_handler): # pragma: no cover
  def checked_cronjob_handler(self, *args):
    assert (self.request.headers.get('X-AppEngine-Cron') or
        users.is_current_user_admin())
    cronjob_handler(self, *args)
  return checked_cronjob_handler

def filter_dict(d, keys): # pragma: no cover
  return {key: d[key] for key in d if key in keys}

def is_valid_user(): # pragma: no cover
  if users.is_current_user_admin():
    return True
  user = users.get_current_user()
  return user and VALID_EMAIL_RE.match(user.email())

def password_sha1(password): # pragma: no cover
  return hashlib.sha1(password).hexdigest()

def to_unix_timestamp(datetime): # pragma: no cover
  return calendar.timegm(datetime.timetuple()) + datetime.microsecond / 1e6

def compressed_json_dump(value, writer): # pragma: no cover
  return json.dump(value, writer, separators=compressed_separators)

def compressed_json_dumps(value): # pragma: no cover
  return json.dumps(value, separators=compressed_separators)
