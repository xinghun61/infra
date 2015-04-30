# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
import os
import webapp2

from google.appengine.api import users
from webapp2_extras import jinja2

from components import auth


def init_local_dev_server():
  members = [
    auth.Identity.from_bytes('anonymous:anonymous'),
    auth.Identity.from_bytes('user:test@example.com'),
    auth.Identity.from_bytes(
        'user:590116423158-ngd238l7s0a6cbpe96oqkjk5hetbbdjn@'
        'developer.gserviceaccount.com')
  ]
  auth.bootstrap_group('service-account-monitoring-proxy', members)
  auth.bootstrap_group('project-chrome-infra-monitoring-team', members)


class BaseAuthHandler(auth.AuthenticatingHandler):
  """Provide a cached Jinja environment to each request."""

  @staticmethod
  def template_params(params=None):
    """Create jinja2 template parameters based on ``params``."""
    account = users.get_current_user()
    data = {
      'username': account.email() if account else None,
      'signin_link': users.create_login_url('/') if not account else None,
      'title': 'Chrome Infra Monitoring Proxy',
    }
    data.update(params or {})
    return data

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
        app=self.app, factory=BaseAuthHandler.jinja2_factory)

  def render_response(self, _template, **context):
    # Renders a template and writes the result to the response.
    context = self.template_params(context)
    rv = self.jinja2.render_template(_template, **context)
    self.response.write(rv)
