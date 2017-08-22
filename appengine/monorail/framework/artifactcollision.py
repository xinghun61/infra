# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Class that implements the artifact update collision page.

This page is displayed only when one user views and edits an issue,
but another user has already submitted an issue update before the
first user submits his/her update.

TODO(jrobbins): give the user better options on how to proceed.

Summary of classes:
  ArtifactCollision: Show an error message explaining the mid-air collision.
"""

import re

from framework import exceptions
from framework import servlet


class ArtifactCollision(servlet.Servlet):
  """ArtifactCollision page explains that a mid-air collision has occured."""

  _PAGE_TEMPLATE = 'framework/artifact-collision-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_NONE

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      A dict of values used by EZT for rendering the page.
    """
    artifact_name = mr.GetParam('name')
    if not artifact_name:
      raise exceptions.InputException()  # someone forged a link

    artifact_detail_url = '/p/%s/issues/detail?id=%s' % (
        mr.project_name, mr.continue_issue_id)

    return {
        'artifact_name': artifact_name,
        'artifact_detail_url': artifact_detail_url,
    }
