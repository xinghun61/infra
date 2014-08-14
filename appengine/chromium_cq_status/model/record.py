# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

class Record(ndb.Model):
  timestamp = ndb.DateTimeProperty(auto_now=True)
  tags = ndb.StringProperty(repeated=True)
  fields = ndb.JsonProperty(default={})
