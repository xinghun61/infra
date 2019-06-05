# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that implement the advanced search feature page.

The advanced search page simply displays an HTML page with a form.
The form handler converts the widget-based query into a googley query
string and redirects the user to the issue list servlet.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import re

from features import savedqueries_helpers
from framework import framework_helpers
from framework import permissions
from framework import servlet
from framework import urls

# Patterns for search values that can be words, labels,
# component paths, or email addresses.
VALUE_RE = re.compile(r'[-a-zA-Z0-9._>@]+')


class IssueAdvancedSearch(servlet.Servlet):
  """IssueAdvancedSearch shows a form to enter an advanced search."""

  _PAGE_TEMPLATE = 'tracker/issue-advsearch-page.ezt'
  _MAIN_TAB_MODE = servlet.Servlet.MAIN_TAB_ISSUES

  # This form *only* redirects to a GET request, and permissions are checked
  # in that handler.
  CHECK_SECURITY_TOKEN = False

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page.

    Args:
      mr: commonly used info parsed from the request.

    Returns:
      Dict of values used by EZT for rendering the page.
    """
    # TODO(jrobbins): Allow deep-linking into this page.
    canned_query_views = []
    if mr.project_id:
      with mr.profiler.Phase('getting canned queries'):
        canned_queries = self.services.features.GetCannedQueriesByProjectID(
            mr.cnxn, mr.project_id)
      canned_query_views = [
          savedqueries_helpers.SavedQueryView(sq, idx + 1, None, None)
          for idx, sq in enumerate(canned_queries)]

    saved_query_views = []
    if mr.auth.user_id and self.services.features:
      with mr.profiler.Phase('getting saved queries'):
        saved_queries = self.services.features.GetSavedQueriesByUserID(
            mr.cnxn, mr.me_user_id)
        saved_query_views = [
            savedqueries_helpers.SavedQueryView(sq, idx + 1, None, None)
            for idx, sq in enumerate(saved_queries)
            if (mr.project_id in sq.executes_in_project_ids or
                not mr.project_id)]

    return {
        'issue_tab_mode': 'issueAdvSearch',
        'page_perms': self.MakePagePerms(mr, None, permissions.CREATE_ISSUE),
        'canned_queries': canned_query_views,
        'saved_queries': saved_query_views,
        }

  def ProcessFormData(self, mr, post_data):
    """Process a posted advanced query form.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to after processing.
    """
    # Default to searching open issues in this project.
    can = post_data.get('can', 2)

    terms = []
    self._AccumulateANDTerm('', 'words', post_data, terms)
    self._AccumulateANDTerm('-', 'without', post_data, terms)
    self._AccumulateANDTerm('label:', 'labels', post_data, terms)
    self._AccumulateORTerm('component:', 'components', post_data, terms)
    self._AccumulateORTerm('status:', 'statuses', post_data, terms)
    self._AccumulateORTerm('reporter:', 'reporters', post_data, terms)
    self._AccumulateORTerm('owner:', 'owners', post_data, terms)
    self._AccumulateORTerm('cc:', 'cc', post_data, terms)
    self._AccumulateORTerm('commentby:', 'commentby', post_data, terms)

    if 'starcount' in post_data:
      starcount = int(post_data['starcount'])
      if starcount >= 0:
        terms.append('starcount:%s' % starcount)

    return framework_helpers.FormatAbsoluteURL(
        mr, urls.ISSUE_LIST, q=' '.join(terms), can=can)

  def _AccumulateANDTerm(self, operator, form_field, post_data, search_query):
    """Build a query that matches issues with ALL of the given field values."""
    user_input = post_data.get(form_field)
    if user_input:
      values = VALUE_RE.findall(user_input)
      search_terms = ['%s%s' % (operator, v) for v in values]
      search_query.extend(search_terms)

  def _AccumulateORTerm(self, operator, form_field, post_data, search_query):
    """Build a query that matches issues with ANY of the given field values."""
    user_input = post_data.get(form_field)
    if user_input:
      values = VALUE_RE.findall(user_input)
      search_term = '%s%s' % (operator, ','.join(values))
      search_query.append(search_term)
