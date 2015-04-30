# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import logging
import os

from google.appengine.ext import ndb

CONFIG_DATA_KEY = 'config_data_key'


class MonAcqData(ndb.Model):
  """Store the sensitive endpoint data."""
  credentials = ndb.JsonProperty()
  url = ndb.StringProperty()
  scopes = ndb.StringProperty(repeated=True)
  headers = ndb.JsonProperty(default={})


def payload_stats(data):
  md5 = hashlib.md5()
  md5.update(data)
  md5hex = md5.hexdigest()
  return 'type=%s, %d bytes, md5=%s' % (type(data), len(data), md5hex)
