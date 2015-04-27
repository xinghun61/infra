# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import logging
import os
import sys
import webapp2

from google.appengine.ext import ndb
from webapp2_extras import jinja2

CONFIG_DATA_KEY = 'config_data_key'


def is_development_server():
  return os.environ.get('SERVER_SOFTWARE', '').startswith('Development')


class MonAcqData(ndb.Model):
  """Store the sensitive endpoint data."""
  credentials = ndb.JsonProperty()
  url = ndb.StringProperty()
  scopes = ndb.StringProperty(repeated=True)
  headers = ndb.JsonProperty(default={})


def payload_stats(data):
  md5 = hashlib.md5()
  md5.update(data)
  md5hex = md5.hexdigest()
  return 'type=%s, %d bytes, md5=%s' % (type(data), len(data), md5hex)


class BaseHandler(webapp2.RequestHandler):
  """Provide a cached Jinja environment to each request."""

  def __init__(self, *args, **kwargs):
    webapp2.RequestHandler.__init__(self, *args, **kwargs)

  @staticmethod
  def jinja2_factory(app):
    template_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), 'templates'))
    config = {'template_path': template_dir}
    jinja = jinja2.Jinja2(app, config=config)
    return jinja

  @webapp2.cached_property
  def jinja2(self):
    # Returns a Jinja2 renderer cached in the app registry.
    return jinja2.get_jinja2(
        app=self.app, factory=BaseHandler.jinja2_factory)

  def render_response(self, _template, **context):
    # Renders a template and writes the result to the response.
    rv = self.jinja2.render_template(_template, **context)
    self.response.write(rv)
