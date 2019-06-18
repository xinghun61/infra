# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Logic for storing and representing issues from external trackers."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import re

from framework.exceptions import InvalidExternalIssueReference


class FederatedIssue(object):
  """Abstract base class for holding one federated issue.

  Each distinct external tracker should subclass this.
  """
  shortlink_re = None

  def __init__(self, shortlink):
    if not self.IsShortlinkValid(shortlink):
      raise InvalidExternalIssueReference(
          'Shortlink does not match any valid tracker: %s' % shortlink)

    self.shortlink = shortlink

  @classmethod
  def IsShortlinkValid(cls, shortlink):
    """Returns whether given shortlink is correctly formatted."""
    if not cls.shortlink_re:
      raise NotImplementedError()
    return re.match(cls.shortlink_re, shortlink)


class GoogleIssueTrackerIssue(FederatedIssue):
  """Holds one Google Issue Tracker issue.

  URL: https://issuetracker.google.com/
  """
  shortlink_re = r'^b\/\d+$'
  url_format = 'https://issuetracker.google.com/issues/{issue_id}'

  def __init__(self, shortlink):
    super(GoogleIssueTrackerIssue, self).__init__(shortlink)
    self.issue_id = int(self.shortlink[2:])

  def ToURL(self):
    return self.url_format.format(issue_id=self.issue_id)

  def Summary(self):
    """Returns a short string description for UI."""
    return 'Google Issue Tracker issue %s.' % self.issue_id


# All supported tracker classes.
_federated_issue_classes = [GoogleIssueTrackerIssue]


def IsShortlinkValid(shortlink):
  """Returns whether the given string is valid for any issue tracker."""
  return any(tracker_class.IsShortlinkValid(shortlink)
      for tracker_class in _federated_issue_classes)


def FromShortlink(shortlink):
  """Returns a FederatedIssue for the first matching tracker.

  If no matching tracker is found, returns None.
  """
  for tracker_class in _federated_issue_classes:
    if tracker_class.IsShortlinkValid(shortlink):
      return tracker_class(shortlink)

  return None
