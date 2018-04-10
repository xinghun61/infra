# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class FlakeIssue(ndb.Model):
  """Tracks an issue that was filed for a particular Flake."""

  # The issue id.
  issue_id = ndb.StringProperty(indexed=True)

  # Track the last time this issue was updated by Findit.
  last_updated_time = ndb.DateTimeProperty(indexed=True)

  def FromMonorailIssue(self, issue):
    """Read fields from third_party.monorail_api.issue into a FlakeIssue.

    Doesn't update the last_updated_time which is updated internally by Findit.
    """
    assert issue.id
    self.issue_id = str(issue.id)
