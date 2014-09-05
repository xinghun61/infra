# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from appengine_module.chromium_cq_status.shared.utils import to_unix_timestamp

class Record(ndb.Model): # pragma: no cover
  timestamp = ndb.DateTimeProperty(auto_now=True)
  tags = ndb.StringProperty(repeated=True)
  fields = ndb.JsonProperty(default={})

  def to_dict(self):
    return {
      'key': self.key.id() if type(self.key.id()) != long else None,
      'timestamp': to_unix_timestamp(self.timestamp),
      'tags': self.tags,
      'fields': self.fields,
    }
