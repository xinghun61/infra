# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from shared.utils import to_unix_timestamp, guess_legacy_codereview_hostname
from shared.config import TAG_CODEREVIEW_HOSTNAME

class Record(ndb.Model): # pragma: no cover
  timestamp = ndb.DateTimeProperty(auto_now=True)
  tags = ndb.StringProperty(repeated=True)
  fields = ndb.JsonProperty(default={})

  def to_dict(self):
    return {
      'key': self.key.id() if not isinstance(self.key.id(), long) else None,
      'timestamp': to_unix_timestamp(self.timestamp),
      'tags': self.tags,
      'fields': self.fields,
    }

  def matches_codereview_hostname(self, codereview_hostname):
    """Returns true if this record matches given codereview_hostname."""
    # TAG_CODEREVIEW_HOSTNAME is template '<key>=%s'.
    expected_key = TAG_CODEREVIEW_HOSTNAME.split('=')[0]
    for tag in self.tags:
      kv = tag.split('=', 1)
      if len(kv) != 2:
        continue  # Not a tag, actually.
      key, value = kv
      if key == expected_key:
        return value == codereview_hostname
    # There was no tag with codereview_hostname key, so it was legacy. Guess the
    # issue.
    actual = guess_legacy_codereview_hostname(self.fields.get('issue', ''))
    return codereview_hostname == actual
