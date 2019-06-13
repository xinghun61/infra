# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Holds logic for external issue tracker references."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import re


def shortlink_is_valid(shortlink):
  """Returns whether the given string is valid for any issue tracker."""
  return any(tracker.IsShortlinkValid(shortlink)
      for tracker in FEDERATED_TRACKERS)


class FederatedTrackerBase(object):
  """Abstract class that defines an interface for federated tracker classes.

  A federated tracker class is meant to be a stateless singleton class - just
  a collection of methods.
  """
  shortlink_re = None

  def __init__(self):
    pass

  def IsShortlinkValid(self, shortlink):
    """Returns whether given shortlink is correctly formatted."""
    if not self.shortlink_re:
      raise NotImplementedError()
    return re.match(self.shortlink_re, shortlink)


class GoogleIssueTracker(FederatedTrackerBase):
  """Handles Google Issue Tracker issues.

  URL: https://issuetracker.google.com/
  """
  shortlink_re = r'^b\/\d+$'

  def __init__(self):
    super(GoogleIssueTracker, self).__init__()

FEDERATED_TRACKERS = [GoogleIssueTracker()]
