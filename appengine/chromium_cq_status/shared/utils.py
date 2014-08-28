# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import hashlib

from google.appengine.api import users

from shared.config import VALID_EMAIL_RE

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
