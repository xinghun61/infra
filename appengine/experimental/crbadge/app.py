# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import webapp2


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


class UserPage(BaseHandler):
  def get(self):
    context = {'title': 'User Page' }
    self.render_response('user.html', **context)


class MainPage(BaseHandler):
  def get(self):
    # TODO: redirect to signed in user... what if not signed in?
    self.redirect('/hinoka@chromium.org')


class BadgePage(BaseHandler):
  def get(self):
    context = {'title': 'Badge Details' }
    self.render_response('badge.html', **context)


app = webapp2.WSGIApplication([
    (r'/([a-z0-9]+@[.a-z]+)', UserPage),
    (r'/b/([a-z0-9]+)', BadgePage),
    ('/', MainPage),
])


