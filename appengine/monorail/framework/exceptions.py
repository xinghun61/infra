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


# TODO(jrobbins): move more exceptions here.
