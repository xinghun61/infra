# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to forward requests to configured urls.

This page handles the /wiki and /source urls which are forwarded from Codesite.
If a project has defined appropriate urls, then the users are forwarded there.
If not, they are redirected to adminIntro.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import httplib

from framework import framework_helpers
from framework import servlet
from framework import urls


class WikiRedirect(servlet.Servlet):
  """Redirect to the wiki documentation, if provided."""

  def get(self, **kwargs):
    """Construct a 302 pointing at project.docs_url, or at adminIntro."""
    if not self.mr.project:
      self.response.status = httplib.NOT_FOUND
      return
    docs_url = self.mr.project.docs_url
    if not docs_url:
      docs_url = framework_helpers.FormatAbsoluteURL(
          self.mr, urls.ADMIN_INTRO, include_project=True)
    self.response.location = docs_url
    self.response.status = httplib.MOVED_PERMANENTLY


class SourceRedirect(servlet.Servlet):
  """Redirect to the source browser, if provided."""

  def get(self, **kwargs):
    """Construct a 302 pointing at project.source_url, or at adminIntro."""
    if not self.mr.project:
      self.response.status = httplib.NOT_FOUND
      return
    source_url = self.mr.project.source_url
    if not source_url:
      source_url = framework_helpers.FormatAbsoluteURL(
          self.mr, urls.ADMIN_INTRO, include_project=True)
    self.response.location = source_url
    self.response.status = httplib.MOVED_PERMANENTLY
