# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Serve robots.txt

This class serves robots.txt dynamically to try to get around a stale version
served by appengine due to the cache configuration.
"""

import datetime
import httplib
import time

from google.appengine.api import app_identity
from google.appengine.api import modules

import webapp2

_ROBOTS_TXT = '''\
# Served by %(version_name)s-dot-%(version_hostname)s on %(date)s
User-agent: *
# Start by disallowing everything.
Disallow: /
# Some specific things are okay, though.
Allow: /$
Allow: /hosting
Allow: /p/*/adminIntro
# Allow files needed to render the new UI
Allow:  /prpc/*
Allow:  /static/*
Allow:  /deployed_node_modules/*
# Query strings are hard. We only allow ?id=N, no other parameters.
Allow: /p/*/issues/detail?id=*
Allow: /p/*/issues/detail_ezt?id=*
Disallow: /p/*/issues/detail?id=*&*
Disallow: /p/*/issues/detail?*&id=*
# 10 second crawl delay for bots that honor it.
Crawl-delay: 10
'''


class Robots(webapp2.RequestHandler):
  def get(self):
    self.response.content_type = 'text/plain'
    self.response.status = httplib.OK

    date = datetime.datetime.utcfromtimestamp(time.time())
    date = date.strftime('%Y-%m-%d %H:%M:%S UTC')
    self.response.write(_ROBOTS_TXT % {
      'version_name': modules.get_current_version_name(),
      'version_hostname': app_identity.get_default_version_hostname(),
      'date': date})
