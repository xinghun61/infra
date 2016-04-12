# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A class to forward requests to the provided documentation url.

This page handles the /wiki urls which are forwarded from Codesite.
If a project has defined a docs_url, then the requests are forwarded there.
If not, they are redirected to adminIntro.
"""

import httplib

from framework import framework_helpers
from framework import servlet
from framework import urls


class WikiRedirect(servlet.Servlet):
  """Redirect to the wiki documentation, if provided."""

  def get(self, **kwargs):
    """Construct a 302 pointing at project.docs_url, or at adminIntro."""
    docs_url = self.mr.project.docs_url
    if not docs_url:
      docs_url = framework_helpers.FormatAbsoluteURL(
          self.mr, urls.ADMIN_INTRO, include_project=True)
    self.response.location = docs_url
    self.response.status = httplib.MOVED_PERMANENTLY
