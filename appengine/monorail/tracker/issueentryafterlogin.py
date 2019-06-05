# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Redirect to /issues/entry or an external URL (like the wizard).
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from framework import servlet
from framework import servlet_helpers


class IssueEntryAfterLogin(servlet.Servlet):
  """Redirect after clicking "New issue" and logging in."""

  # Note: This servlet does not use an HTML template.

  def GatherPageData(self, mr):
    """Build up a dictionary of data values to use when rendering the page."""
    if not mr.auth.user_id:
      self.abort(400, 'Only signed-in users should reach this URL.')

    with mr.profiler.Phase('getting config'):
      config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
    entry_page_url = servlet_helpers.ComputeIssueEntryURL(mr, config)
    logging.info('Redirecting to %r', entry_page_url)
    self.redirect(entry_page_url, abort=True)
