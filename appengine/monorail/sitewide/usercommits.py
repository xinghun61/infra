# Copyright 2016 The Chromium Authors. All rights remake served.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Cron job that adds all new user commmits to the SQL database daily."""

import json
import logging
from google.appengine.api import urlfetch
import webapp2


class GetCommitsCron(webapp2.RequestHandler):

  """Fetches commit data from Gitiles and adds it to the CloudSQL database
  """
  def get(self):
    url = 'https://gerrit.googlesource.com/gerrit/+log/?format=JSON'
    try:
      result = urlfetch.fetch(url)
      if result.status_code == 200:
        self.response.write(result.content)
      else:
        self.response.status_code = result.status_code
    except urlfetch.Error:
        logging.exception('Caught exception fetching url')
