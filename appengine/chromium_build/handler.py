# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urllib

from google.appengine.ext import deferred
import webapp2

import app
import base_page
import gae_ts_mon
import utils

from third_party.BeautifulSoup.BeautifulSoup import BeautifulSoup

ONE_BOX_URL = 'horizontal_one_box_per_builder'

class PageAction(base_page.BasePage):

  # W0221: 44,2:PageAction.get: Arguments number differs from overridden method
  # pylint: disable=W0221
  def get(self, localpath):
    page_data = self._do_almost_everything(localpath)
    if page_data is not None:
      self.response.out.write(page_data.get('content'))


  def cache_merged_console(self, localpath):
    # Remove any query args that we don't want to keep.
    VARY_ARGS = ['numrevs=']
    args = self.request.query_string.split('&')
    args = [arg for arg in args if any([arg.startswith(pre) for pre in
                                        VARY_ARGS])]
    if args:
      localpath += '?' + '&'.join(args)
    # See if we already have the appropriate page cached.
    unquoted_localpath = urllib.unquote(localpath)
    page_data = app.get_and_cache_pagedata(unquoted_localpath)
    # If we got the page and it was generated recently enough, just serve that.
    if page_data.get('content') and recent_page(page_data):
      return page_data
    # If they specified a number of revs, figure out how many they want.
    num_revs = self.request.get('numrevs')
    if num_revs:
      num_revs = utils.clean_int(num_revs, -1)
      if num_revs <= 0:
        num_revs = None
    app.console_merger(unquoted_localpath, 'console/chromium', page_data,
                       num_rows_to_merge=num_revs)
    return app.get_and_cache_pagedata(unquoted_localpath)


  def _do_almost_everything(self, localpath):
    # Does almost all of the work except for writing the content to
    # the response. Returns the page_data, or None either if an error
    # occurred or if the processing of the request was fully handled
    # in this method (this is done for the console).
    unquoted_localpath = urllib.unquote(localpath)
    if self.request.path.endswith('/chromium/console'):
      page_data = self.cache_merged_console(unquoted_localpath)
    else:
      page_data = app.get_and_cache_pagedata(unquoted_localpath)
    if page_data.get('content') is None:
      app.logging.error('Page %s not found.' % unquoted_localpath)
      self.error(404)  # file not found
      return None

    self.response.headers['Content-Type'] = app.path_to_mime_type(
        unquoted_localpath)
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
      return None
    self.response.headers['Cache-Control'] = 'public, max-age=60'
    self.response.headers['Pragma'] = 'Public'
    return page_data

class OneBoxAction(PageAction):
  def _do_almost_everything(self, localpath):
    page_data = super(OneBoxAction, self)._do_almost_everything(
      localpath + '/' + ONE_BOX_URL)
    if page_data:
      builders = self.request.GET.getall('builder')
      if builders and len(builders):
        one_box = BeautifulSoup(page_data['content'])
        all_tds = one_box.findAll('td')
        for td in all_tds:
          if td.a and td.a['title'] not in builders:
            td.extract()
        page_data['content'] = self.ContentsToHtml(one_box)
    return page_data

  @staticmethod
  def ContentsToHtml(contents):
    return ''.join(unicode(content).encode('ascii', 'replace')
                   for content in contents)


def recent_page(page_data):
  ts = page_data.get('fetch_timestamp')
  if not ts:
    return False
  now = app.datetime.datetime.now()
  if isinstance(ts, app.datetime.datetime):
    delta = now - ts
  else:
    delta = now - app.datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f")
  return delta < app.datetime.timedelta(minutes=1)


class FetchPagesAction(base_page.BasePage):

  # R0201: 93,2:FetchPagesAction.get: Method could be a function
  # pylint: disable=R0201
  def get(self):
    deferred.defer(app.fetch_pages)


class MainAction(base_page.BasePage):

  def get(self):
    args = self.request.query_string
    self.redirect('/p/chromium/console' + '?' + args)


# Call initial bootstrap for the app module.
app.bootstrap()
base_page.bootstrap()

# GAE will cache |application| across requests if we set it here.  See
# http://code.google.com/appengine/docs/python/runtime.html#App_Caching for more
# info.
application = webapp2.WSGIApplication(
  [('/', MainAction),
   ('/p/(.*)/' + ONE_BOX_URL, OneBoxAction),
   ('/p/(.*)', PageAction),
   ('/tasks/fetch_pages', FetchPagesAction)])
gae_ts_mon.initialize(application)
