# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

# Mapping between luci project and monorail project.
_LUCI_PROJECT_TO_MONORAIL_PROJECT = {'chromium': 'chromium'}


class FlakeIssue(ndb.Model):
  """Tracks a Monorail issue for a particular Flake."""

  # Project name for Monorail: https://bugs.chromium.org/hosting.
  # For example: 'chromium'.
  monorail_project = ndb.StringProperty(required=True)

  # The issue id.
  issue_id = ndb.IntegerProperty(required=True)

  # Track the last time this issue was created or updated by Findit.
  last_updated_time = ndb.DateTimeProperty(required=True, auto_now_add=True)

  @staticmethod
  def GetId(monorail_project, issue_id):
    return '%s@%s' % (monorail_project, issue_id)

  @classmethod
  def Create(cls, monorail_project, issue_id):
    """Creates a FlakeIssue entity for a Monorail issue."""
    flake_issue_id = cls.GetId(monorail_project, issue_id)
    return cls(
        monorail_project=monorail_project, issue_id=issue_id, id=flake_issue_id)

  @staticmethod
  def GetMonorailProjectFromLuciProject(luci_project):
    """Given a luci project, returns the corresponding monorail project.

    Args:
      luci_project: A luci project name.

    Returns:
      The corresponding monorail project name if it exists in the mapping,
      otherwise None.
    """
    return _LUCI_PROJECT_TO_MONORAIL_PROJECT.get(luci_project, None)
