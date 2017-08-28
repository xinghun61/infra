# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import os
import re
import sys
import webapp2

sys.path.insert(0, os.path.join(
  os.path.dirname(os.path.dirname(__file__)), 'third_party'))

import cloudstorage


BUCKET = '/flake-predictor-data/log_data'
DAYS = 7


def _delete_old_files(bucket, now, days=0, hours=0, minutes=0):
  for file_stat in cloudstorage.listbucket(bucket):
    time_uploaded = datetime.datetime.strptime(
        datetime.datetime.fromtimestamp(
            file_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
        '%Y-%m-%d %H:%M:%S')
    if now - time_uploaded >= datetime.timedelta(
        days=days, hours=hours, minutes=minutes):
      cloudstorage.delete(file_stat.filename)

class CleanupGCSHandler(webapp2.RequestHandler):
  def get(self):
    _delete_old_files(BUCKET, datetime.datetime.utcnow(), days=DAYS)
