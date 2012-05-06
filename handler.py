# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os.path
import urllib

from google.appengine.ext import deferred
# F0401:  9,0: Unable to import 'webapp2'
# pylint: disable=F0401
import webapp2
from google.appengine.ext.webapp import template

import app

def _clean_int(value, default):
  """Convert a value to an int, or the default value if conversion fails."""
  try:
    return int(value)
  except (TypeError, ValueError):
    return default


# W0232: 23,0:MyRequestHandler: Class has no __init__ method
# pylint: disable=W0232
class MyRequestHandler(webapp2.RequestHandler):
  """Base request handler with this application specific helpers."""

  # E1101: 31,4:MyRequestHandler._render_template: Instance of
  # 'MyRequestHandler' has no 'response' member
  # pylint: disable=E1101
  def _render_template(self, name, values):
    """
    Wrapper for template.render that updates response
    and knows where to look for templates.
    """
    self.response.out.write(template.render(
        os.path.join(os.path.dirname(__file__), 'templates', name),
        values))


# W0232: 42,0:PageAction: Class has no __init__ method
# pylint: disable=W0232
class PageAction(MyRequestHandler):

  # W0221: 44,2:PageAction.get: Arguments number differs from overridden method
  # pylint: disable=W0221
  def get(self, localpath):
    # E1101: 70,11:PageAction.get: Instance of 'PageAction' has no 'request'
    # member
    # pylint: disable=E1101
    if len(self.request.query_string) > 0:
      # E1101: 47,11:PageAction.get: Instance of 'PageAction' has no 'request'
      # member
      # pylint: disable=E1101
      localpath += '?' + self.request.query_string
    unquoted_localpath = urllib.unquote(localpath)
    content = app.get_and_cache_page(unquoted_localpath)
    if content is None:
      # E1101: 78,6:PageAction.get: Instance of 'PageAction' has no 'error'
      # member
      # pylint: disable=E1101
      self.error(404)  # file not found
      return

    # Make the Google Frontend capable of caching this request for 60 seconds.
    # TODO: Caching is not working yet.
    # E1101: 83,4:PageAction.get: Instance of 'PageAction' has no 'response'
    # member
    # pylint: disable=E1101
    self.response.headers['Cache-Control'] = 'public, max-age=60'
    # E1101: 83,4:PageAction.get: Instance of 'PageAction' has no 'response'
    # member
    # pylint: disable=E1101
    self.response.headers['Pragma'] = 'Public'
    # E1101: 83,4:PageAction.get: Instance of 'PageAction' has no 'response'
    # member
    # pylint: disable=E1101
    self.response.headers['Content-Type'] = app.path_to_mime_type(
        unquoted_localpath)
    self.response.out.write(content)



class FetchPagesAction(MyRequestHandler):

  # R0201: 93,2:FetchPagesAction.get: Method could be a function
  # pylint: disable=R0201
  def get(self):
    deferred.defer(app.fetch_pages)


class MainAction(MyRequestHandler):

  def get(self):
    # E1101: 96,4:MainAction.get: Instance of 'MainAction' has no 'redirect'
    # member
    # pylint: disable=E1101
    self.redirect('/p/chromium/console')


# Call initial bootstrap for the app module.
app.bootstrap()

# GAE will cache |application| across requests if we set it here.  See
# http://code.google.com/appengine/docs/python/runtime.html#App_Caching for more
# info.
application = webapp2.WSGIApplication(
  [('/', MainAction),
   ('/p/(.*)', PageAction),
   ('/tasks/fetch_pages', FetchPagesAction)])
