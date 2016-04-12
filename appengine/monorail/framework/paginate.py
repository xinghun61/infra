# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes that help display pagination widgets for result sets."""

import logging

from third_party import ezt

import settings
from framework import framework_helpers


class VirtualPagination(object):
  """Class to calc Prev and Next pagination links based on result counts."""

  def __init__(self, mr, total_count, items_per_page,
               list_page_url=None, count_up=True,
               start_param='start', num_param='num', max_num=None):
    """Given 'num' and 'start' params, determine Prev and Next links.

    Args:
      mr: commonly used info parsed from the request.
      total_count: total number of artifacts that satisfy the query.
      items_per_page: number of items to display on each page, e.g., 25.
      list_page_url: URL of the web application page that is displaying
        the list of artifacts.  Used to build the Prev and Next URLs.
        If None, no URLs will be built.
      count_up: if False, count down from total_count.
      start_param: query string parameter name to use for the start
        of the pagination page.
      num_param: query string parameter name to use for the number of items
        to show on a pagination page.
      max_num: optional limit on the value of the num param.  If not given,
        settings.max_artifact_search_results_per_page is used.
    """
    self.total_count = total_count
    self.prev_url = ''
    self.reload_url = ''
    self.next_url = ''

    if max_num is None:
      max_num = settings.max_artifact_search_results_per_page

    self.num = mr.GetPositiveIntParam(num_param, items_per_page)
    self.num = min(self.num, max_num)

    if count_up:
      self.start = mr.GetPositiveIntParam(start_param, 0)
      self.last = min(self.total_count, self.start + self.num)
      prev_start = max(0, self.start - self.num)
      next_start = self.start + self.num
    else:
      self.start = mr.GetPositiveIntParam(start_param, self.total_count)
      self.last = max(0, self.start - self.num)
      prev_start = min(self.total_count, self.start + self.num)
      next_start = self.start - self.num

    if list_page_url:
      if mr.project_name:
        list_servlet_rel_url = '/p/%s%s' % (
            mr.project_name, list_page_url)
      else:
        list_servlet_rel_url = list_page_url

      self.reload_url = framework_helpers.FormatURL(
          mr, list_servlet_rel_url,
          **{start_param: self.start, num_param: self.num})

      if prev_start != self.start:
        self.prev_url = framework_helpers.FormatURL(
            mr, list_servlet_rel_url,
            **{start_param: prev_start, num_param: self.num})
      if ((count_up and next_start < self.total_count) or
          (not count_up and next_start >= 1)):
        self.next_url = framework_helpers.FormatURL(
            mr, list_servlet_rel_url,
            **{start_param: next_start, num_param: self.num})

    self.visible = ezt.boolean(self.last != self.start)

    # Adjust indices to one-based values for display to users.
    if count_up:
      self.start += 1
    else:
      self.last += 1

  def DebugString(self):
    """Return a string that is useful in on-page debugging."""
    return '%s - %s of %s; prev_url:%s; next_url:%s' % (
        self.start, self.last, self.total_count, self.prev_url, self.next_url)


class ArtifactPagination(VirtualPagination):
  """Class to calc Prev and Next pagination links based on a results list."""

  def __init__(
      self, mr, results, items_per_page, list_page_url, total_count=None,
      limit_reached=False, skipped=0):
    """Given 'num' and 'start' params, determine Prev and Next links.

    Args:
      mr: commonly used info parsed from the request.
      results: a list of artifact ids that satisfy the query.
      items_per_page: number of items to display on each page, e.g., 25.
      list_page_url: URL of the web application page that is displaying
        the list of artifacts.  Used to build the Prev and Next URLs.
      total_count: specify total result count rather than the length of results
      limit_reached: optional boolean that indicates that more results could
        not be fetched because a limit was reached.
      skipped: optional int number of items that were skipped and left off the
        front of results.
    """
    if total_count is None:
      total_count = skipped + len(results)
    super(ArtifactPagination, self).__init__(
        mr, total_count, items_per_page, list_page_url=list_page_url)

    self.limit_reached = ezt.boolean(limit_reached)
    # Determine which of those results should be visible on the current page.
    range_start = self.start - 1 - skipped
    range_end = range_start + self.num
    assert 0 <= range_start <= range_end
    self.visible_results = results[range_start:range_end]
