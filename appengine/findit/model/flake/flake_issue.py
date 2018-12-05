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

  # The key to the associated culprit identified by flake analysis, if any.
  flake_culprit_key = ndb.KeyProperty(kind='FlakeCulprit')

  # Track the last time this issue was created or updated by Flake Detection.
  # This field is needed because Flake Detection can only create/update an issue
  # at most once every 24 hours.
  last_updated_time_by_flake_detection = ndb.DateTimeProperty()

  # Key to the FINAL destination of merging chain that this issue is a part of.
  # For example, if FlakeIssueA merged into FlakeIssueB (FlakeIssueB is not
  # merged into any other issue), the value would be key to FlakeIssueB;
  # And if FlakeIssueC is merged into FlakeIssueD, and FlakeIssueD is merged
  # into FlakeIssueE, both FlakeIssueC and FlakeIssueD should store the key to
  # FlakeIssueE as their merge_destination_key.
  # Puts FlakeIssue in quotes because the key refers to the same data model.
  merge_destination_key = ndb.KeyProperty(kind='FlakeIssue', indexed=True)

  # The most recent updated time the issue was updated in Monorail. Indexed for
  # querying by timestamp.
  last_updated_time_in_monorail = ndb.DateTimeProperty(indexed=True)

  # The status of the issue in monorail, e.g. 'Assigned'. Indexed for querying
  # by status.
  status = ndb.StringProperty(indexed=True)

  # The priority of the bug.
  priority = ndb.IntegerProperty(indexed=False)

  @staticmethod
  def _CreateKey(monorail_project, issue_id):  # pragma: no cover
    return ndb.Key(FlakeIssue, '%s@%d' % (monorail_project, issue_id))

  @staticmethod
  def Create(monorail_project, issue_id):
    """Creates a FlakeIssue entity for a Monorail issue."""
    return FlakeIssue(
        monorail_project=monorail_project,
        issue_id=issue_id,
        key=FlakeIssue._CreateKey(monorail_project, issue_id))

  @staticmethod
  def Get(monorail_project, issue_id):
    return FlakeIssue._CreateKey(monorail_project, issue_id).get()

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

  def GetMergeDestination(self):
    """Gets the FlakeIssue entity of this issue's final merged destination."""
    return self.merge_destination_key.get(
    ) if self.merge_destination_key else None

  def GetMostUpdatedIssue(self):
    return self.GetMergeDestination() or self

  def Update(self, **kwargs):
    """Updates arbitrary fields as specified in kwargs."""
    any_changes = False

    for arg, value in kwargs.iteritems():
      current_value = getattr(self, arg, None)
      if current_value != value:
        setattr(self, arg, value)
        any_changes = True

    if any_changes:
      self.put()
