# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""This file sets up all the urls for monorail pages."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


import httplib
import logging

import webapp2


def MakeRedirect(redirect_to_this_uri, permanent=True):
  """Return a new request handler class that redirects to the given URL."""

  class Redirect(webapp2.RequestHandler):
    """Redirect is a response handler that issues a redirect to another URI."""

    def get(self, **_kw):
      """Send the 301/302 response code and write the Location: redirect."""
      self.response.location = redirect_to_this_uri
      self.response.headers.add('Strict-Transport-Security',
          'max-age=31536000; includeSubDomains')
      self.response.status = (
          httplib.MOVED_PERMANENTLY if permanent else httplib.FOUND)

  return Redirect


def MakeRedirectInScope(uri_in_scope, scope, permanent=True, keep_qs=False):
  """Redirect to a URI within a given scope, e.g., per project or user.

  Args:
    uri_in_scope: a uri within a project or user starting with a slash.
    scope: a string indicating the uri-space scope:
      p for project pages
      u for user pages
      g for group pages
    permanent: True for a HTTP 301 permanently moved response code,
      otherwise a HTTP 302 temporarily moved response will be used.
    keep_qs: set to True to make the redirect retain the query string.
      When true, permanent is ignored.

  Example:
    self._SetupProjectPage(
      redirect.MakeRedirectInScope('/newpage', 'p'), '/oldpage')

  Returns:
    A class that can be used with webapp2.
  """
  assert uri_in_scope.startswith('/')

  class RedirectInScope(webapp2.RequestHandler):
    """A handler that redirects to another URI in the same scope."""

    def get(self, **_kw):
      """Send the 301/302 response code and write the Location: redirect."""
      split_path = self.request.path.lstrip('/').split('/')
      if len(split_path) > 1:
        project_or_user = split_path[1]
        url = '//%s/%s/%s%s' % (
            self.request.host, scope, project_or_user, uri_in_scope)
      else:
        url = '/'
      if keep_qs and self.request.query_string:
        url += '?' + self.request.query_string
      self.response.location = url

      self.response.headers.add('Strict-Transport-Security',
          'max-age=31536000; includeSubDomains')
      if permanent and not keep_qs:
        self.response.status = httplib.MOVED_PERMANENTLY
      else:
        self.response.status = httplib.FOUND

  return RedirectInScope
