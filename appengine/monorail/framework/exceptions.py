# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Exception classes used throughout monorail.
"""

class Error(Exception):
  """Base class for errors from this module."""
  pass


class InputException(Error):
  """Error in user input processing."""
  pass


class ProjectAlreadyExists(Error):
  """Tried to create a project that already exists."""


class NoSuchProjectException(Error):
  """No project with the specified name exists."""
  pass


class NoSuchIssueException(Error):
  """The requested issue was not found."""
  pass


class NoSuchAttachmentException(Error):
  """The requested attachment was not found."""
  pass


class NoSuchCommentException(Error):
  """The requested comment was not found."""
  pass


class MidAirCollisionException(Error):
  """The item was updated by another user at the same time."""

  def __init__(self, name, continue_issue_id):
    super(MidAirCollisionException, self).__init__()
    self.name = name  # human-readable name for the artifact being edited.
    self.continue_issue_id = continue_issue_id  # ID of issue to start over.
