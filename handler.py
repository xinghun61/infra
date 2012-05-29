# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urllib

from google.appengine.ext import deferred
# F0401:  9,0: Unable to import 'webapp2'
# pylint: disable=F0401
import webapp2

import app
import base_page
import utils


class PageAction(base_page.BasePage):

  # W0221: 44,2:PageAction.get: Arguments number differs from overridden method
  # pylint: disable=W0221
  def get(self, localpath):
    if len(self.request.query_string) > 0:
      # The reload arg, if present, must be stripped from the URL.
      args = self.request.query_string.split('&')
      args = [arg for arg in args if not arg.startswith('reload=')]
      if args:
        localpath += '?' + '&'.join(args)
    unquoted_localpath = urllib.unquote(localpath)
    page_data = app.get_and_cache_pagedata(unquoted_localpath)
    if page_data.get('content') is None:
      self.error(404)  # file not found
      return

    self.response.headers['Content-Type'] = app.path_to_mime_type(
        unquoted_localpath)
    template_values = self.InitializeTemplate()
    if self.request.path.endswith('/console'):
      template_values = self.InitializeTemplate()
      template_values['body_class'] = page_data.get('body_class')
      template_values['content'] = page_data.get('content')
      template_values['offsite_base'] = page_data.get('offsite_base')
      template_values['title'] = page_data.get('title')
      if self.user:
        reloadarg = utils.clean_int(self.request.get('reload'), -1)
        if reloadarg != -1:
          reloadarg = max(reloadarg, 30)
          template_values['reloadarg'] = reloadarg
      else:
        # Make the Google Frontend capable of caching this request for 60
        # seconds.
        # TODO: Caching is not working yet.
        self.response.headers['Cache-Control'] = 'public, max-age=60'
        self.response.headers['Pragma'] = 'Public'
      self.DisplayTemplate('base.html', template_values)
      return

    # Make the Google Frontend capable of caching this request for 60 seconds.
    # TODO: Caching is not working yet.
    self.response.headers['Cache-Control'] = 'public, max-age=60'
    self.response.headers['Pragma'] = 'Public'
    self.response.out.write(page_data.get('content'))



class FetchPagesAction(base_page.BasePage):

  # R0201: 93,2:FetchPagesAction.get: Method could be a function
  # pylint: disable=R0201
  def get(self):
    deferred.defer(app.fetch_pages)


class MainAction(base_page.BasePage):

  def get(self):
    self.redirect('/p/chromium/console')


# Call initial bootstrap for the app module.
app.bootstrap()
base_page.bootstrap()

# GAE will cache |application| across requests if we set it here.  See
# http://code.google.com/appengine/docs/python/runtime.html#App_Caching for more
# info.
application = webapp2.WSGIApplication(
  [('/', MainAction),
   ('/p/(.*)', PageAction),
   ('/tasks/fetch_pages', FetchPagesAction)])
