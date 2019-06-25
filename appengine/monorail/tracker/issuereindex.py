# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement an admin utility to re-index issues in bulk."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import urllib

import settings
from framework import permissions
from framework import servlet
from framework import urls
from services import tracker_fulltext


class IssueReindex(servlet.Servlet):
  """IssueReindex shows a form to request that issues be indexed."""

  _PAGE_TEMPLATE = 'tracker/issue-reindex-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ISSUES

  def AssertBasePermission(self, mr):
    """Check whether the user has any permission to visit this page.

    Args:
      mr: commonly used info parsed from the request.
    """
    super(IssueReindex, self).AssertBasePermission(mr)
    if not self.CheckPerm(mr, permissions.EDIT_PROJECT):
      raise permissions.PermissionException(
          'You are not allowed to administer this project')

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    return {
        # start and num are already passed to the template.
        'issue_tab_mode': None,
        'auto_submit': mr.auto_submit,
        'page_perms': self.MakePagePerms(mr, None, permissions.CREATE_ISSUE),
        }

  def ProcessFormData(self, mr, post_data):
    """Process a posted issue reindex form.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to after processing. The URL will contain
      a new start that is auto-incremented using the specified num value.
    """
    start = max(0, int(post_data['start']))
    num = max(0, min(settings.max_artifact_search_results_per_page,
                     int(post_data['num'])))

    issues = self.services.issue.GetIssuesByLocalIDs(
        mr.cnxn, mr.project_id, list(range(start, start + num)))
    logging.info('got %d issues to index', len(issues))
    if issues:
      tracker_fulltext.IndexIssues(
          mr.cnxn, issues, self.services.user, self.services.issue,
          self.services.config)

    # Make the browser keep submitting the form, if the user wants that,
    # and we have not run out of issues to process.
    auto_submit = issues and ('auto_submit' in post_data)

    query_map = {
      'start': start + num,  # auto-increment start.
      'num': num,
      'auto_submit': bool(auto_submit),
    }
    return '/p/%s%s?%s' % (mr.project_name, urls.ISSUE_REINDEX,
                           urllib.urlencode(query_map))
