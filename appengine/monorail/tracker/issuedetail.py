# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the web components issue detail page.

Summary of classes:
  IssueDetail: Show one issue in detail w/ all metadata and comments, and
               process additional comments or metadata changes on it.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


import logging

from framework import servlet
from framework import framework_helpers
from framework import urls


class IssueDetail(servlet.Servlet):

  _PAGE_TEMPLATE = 'tracker/issue-approval-page.ezt'

  def AssertBasePermission(self, mr):
    """Check that the user has permission to visit this page."""
    super(IssueDetail, self).AssertBasePermission(mr)

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    return {
       'local_id': mr.local_id,
       'other_ui_path': 'issues/detail_ezt',
        }


class IssueDetailRedirect(servlet.Servlet):
  def GatherPageData(self, mr):
    logging.info(
        'Redirecting from approval page to the new issue detail page.')
    url = framework_helpers.FormatAbsoluteURL(
        mr, urls.ISSUE_DETAIL, id=mr.local_id)
    return self.redirect(url, abort=True)
