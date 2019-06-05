# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Exception classes used throughout monorail.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

class Error(Exception):
  """Base class for errors from this module."""
  pass


class ActionNotSupported(Error):
  """The user is trying to do something we do not support yet."""
  pass


class InputException(Error):
  """Error in user input processing."""
  pass


class ProjectAlreadyExists(Error):
  """Tried to create a project that already exists."""


class NoSuchProjectException(Error):
  """No project with the specified name exists."""
  pass


class NoSuchTemplateException(Error):
  """No template with the specified name exists."""
  pass


class NoSuchUserException(Error):
  """No user with the specified name exists."""
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


class NoSuchAmendmentException(Error):
  """The requested amendment was not found."""
  pass


class NoSuchComponentException(Error):
  """No component with the specified name exists."""
  pass


class InvalidComponentNameException(Error):
  """The component name is invalid."""
  pass


class InvalidHotlistException(Error):
  """The specified hotlist is invalid."""
  pass


class NoSuchFieldDefException(Error):
  """No field def for specified project exists."""
  pass


class InvalidFieldTypeException(Error):
  """Expected field type and actual field type do not match."""
  pass


class NoSuchIssueApprovalException(Error):
  """The requested approval for the issue was not found."""
  pass


class CircularGroupException(Error):
  """Circular nested group exception."""
  pass


class GroupExistsException(Error):
  """Group already exists exception."""
  pass


class NoSuchGroupException(Error):
  """Requested group was not found exception."""
  pass


class MidAirCollisionException(Error):
  """The item was updated by another user at the same time."""

  def __init__(self, name, continue_issue_id):
    super(MidAirCollisionException, self).__init__()
    self.name = name  # human-readable name for the artifact being edited.
    self.continue_issue_id = continue_issue_id  # ID of issue to start over.


class InvalidExternalIssueReference(Error):
  """Improperly formatted external issue reference.

  External issue references must be of the form:

      $tracker_shortname/$tracker_specific_id

  For example, issuetracker.google.com issues:

      b/123456789
  """
  pass
