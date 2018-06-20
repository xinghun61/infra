# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the issue approval page.

Summary of classes:
  IssueApproval: Show one issue in detail w/ all metadata and comments, and
               process additional comments or metadata changes on it.
"""

from framework import servlet

class IssueApproval(servlet.Servlet):

  _PAGE_TEMPLATE = 'tracker/issue-approval-page.ezt'

  def AssertBasePermission(self, mr):
    """Check that the user has permission to visit this page."""
    super(IssueApproval, self).AssertBasePermission(mr)

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    return {
       'local_id': mr.local_id,
        }
