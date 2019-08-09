# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement a web components page.

Summary of classes:
 WebComponentsPage: Show one web components page.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


import logging

from framework import servlet
from framework import framework_helpers
from framework import urls


class WebComponentsPage(servlet.Servlet):

  _PAGE_TEMPLATE = 'tracker/web-components-page.ezt'

  def AssertBasePermission(self, mr):
    """Check that the user has permission to visit this page."""
    super(WebComponentsPage, self).AssertBasePermission(mr)

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    # Create link to view in old UI for grid view
    is_grid = ''
    old_ui_url = ''
    if mr.mode == 'grid':
      is_grid = 'grid'
      old_ui_url = self.request.url.replace('/list_new', '/list')

    return {
       'local_id': mr.local_id,
       'is_grid': is_grid,
       'old_ui_url': old_ui_url,
        }


class IssueDetailRedirect(servlet.Servlet):
  def GatherPageData(self, mr):
    logging.info(
        'Redirecting from approval page to the new issue detail page.')
    url = framework_helpers.FormatAbsoluteURL(
        mr, urls.ISSUE_DETAIL, id=mr.local_id)
    return self.redirect(url, abort=True)
