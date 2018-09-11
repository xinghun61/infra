# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs.appengine_util import IsStaging

# Mapping between luci project and monorail project.
_LUCI_PROJECT_TO_MONORAIL_PROJECT = {'chromium': 'chromium'}


class FlakeIssue(ndb.Model):
  """Tracks a Monorail issue for a particular Flake."""

  # Project name for Monorail: https://bugs.chromium.org/hosting.
  # For example: 'chromium'.
  monorail_project = ndb.StringProperty(required=True)

  # The issue id.
  issue_id = ndb.IntegerProperty(required=True)

  # Track the last time this issue was created or updated by Flake Detection.
  # This field is needed because Flake Detection can only create/update an issue
  # at most once every 24 hours.
  last_updated_time_by_flake_detection = ndb.DateTimeProperty()

  @classmethod
  def Create(cls, monorail_project, issue_id):
    """Creates a FlakeIssue entity for a Monorail issue."""
    return cls(monorail_project=monorail_project, issue_id=issue_id)

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

  @staticmethod
  def GetLinkForIssue(monorail_project, issue_id):
    """Given a project and issue id, gets a link to the issue on Monorail.

    Args:
      monorail_project: Project name of the issue on Monorail.
      issue_id: Id of the issue.

    Returns:
      A link to the issue on Monorail.
    """
    assert monorail_project, "A valid project is required."

    url_template = 'https://monorail-%s.appspot.com/p/%s/issues/detail?id=%d'
    suffix = 'staging' if IsStaging() else 'prod'

    return url_template % (suffix, monorail_project, issue_id)
