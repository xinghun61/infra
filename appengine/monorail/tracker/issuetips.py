# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to render a page of issue tracker search tips."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from framework import servlet
from framework import permissions


class IssueSearchTips(servlet.Servlet):
  """IssueSearchTips on-line help on how to use issue search."""

  _PAGE_TEMPLATE = 'tracker/issue-search-tips.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ISSUES

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""

    return {
        'issue_tab_mode': 'issueSearchTips',
        'page_perms': self.MakePagePerms(mr, None, permissions.CREATE_ISSUE),
    }
