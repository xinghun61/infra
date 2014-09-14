# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

import webapp2
from webapp2_extras import jinja2

from appengine_module.cr_rev import controller


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
    return jinja2.get_jinja2(app=self.app, factory=BaseHandler.jinja2_factory)

  def render_response(self, _template, **context):
    # Renders a template and writes the result to the response.
    rv = self.jinja2.render_template(_template, **context)
    self.response.write(rv)


class StartPage(BaseHandler):
  def get(self):
    context = {'title': 'cr-rev' }
    self.render_response('main.html', **context)


class MainPage(BaseHandler):
  def get(self):
    context = {'title': 'cr-rev' }
    self.render_response('main.html', **context)


class Redirect(BaseHandler):
  def get(self, query, extra_paths):
    if self.request.referer:
      logging.info('referer is %s' % self.request.referer)
    redirect = controller.calculate_redirect(query)
    if redirect:
      redirect_url = str(redirect.redirect_url)
      if extra_paths:
        redirect_url = redirect_url + extra_paths
      if self.request.query_string:
        redirect_url = redirect_url + '?' + self.request.query_string
      logging.info('redirecting to %s' % redirect_url)
      self.redirect(redirect_url)
    else:
      self.abort(404)
