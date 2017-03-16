# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class CodeReview(object):  # pragma: no cover.
  """Abstract class to interact with code review."""

  def __init__(self, server_hostname):
    """
    Args:
      server_hostname (str): The hostname of the codereview server, eg:
          codereview.chromium.org or chromium-review.googlesource.com.
    """
    self._server_hostname = server_hostname

  def GetCodeReviewUrl(self, change_id):
    """Gets the code review url for a change.

    Args:
      change_id (str or int): The change id of the CL on Gerrit or the issue
          number of the CL on Rietveld.

    Returns:
      The code review url for the change.
    """
    raise NotImplementedError()

  def PostMessage(self, change_id, message):
    """Posts the given message to the CL codereview of the given change id.

    Args:
      change_id (str or int): The change id of the CL on Gerrit or the issue
          number of the CL on Rietveld.
      message(str): The message to be posted to the codereview.
    """
    raise NotImplementedError()

  def CreateRevert(self, reason, change_id, patchset_id=None):
    """Creates a revert CL for the given issue and patchset.

    Args:
      reason (str): A message as the reason for the revert.
      change_id (str or int): The change id on Gerrit or the issue id on
          Rietveld to create the revert for.
      patchset_id (int): The patchset id on Rietveld to create the revert for.
          Optional for Gerrit.

    Returns:
      The change id (or issue id) of the revert CL, or None upon failures.
    """
    raise NotImplementedError()

  def AddReviewers(self, change_id, reviewers, message=None):
    """Adds a list of users to the CL of the specified url as reviewers.

    Args:
      change_id (str or int): The change id on Gerrit or the issue id on
          Rietveld to add reviewers to.
      reviewers (list of str): The emails of the users to be added as reviewers.
      message(str): (optional) The message to be posted to the codereview.

    Returns:
      A boolean indicating success.
    """
    raise NotImplementedError()

  def GetClDetails(self, change_id):
    """Retrieves information about commits and reverts for a given CL.

    Args:
      change_id (str or int): The change id of the CL on Gerrit or the issue
          number of the CL on Rietveld.

    Returns:
      An object that has a `commits` and a `reverts` properties which are lists
      of objects that map a patchset to a revision, and a patchset to a revert
      CL.
    """
    raise NotImplementedError()
