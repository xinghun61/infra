# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file handles serving the list of committers to users."""

__author__ = 'agable@google.com (Aaron Gable)'


import base64
import json
import logging
import os

import endpoints
import jinja2
import webapp2

from google.appengine.api import users

from appengine_module.chromium_committers import auth_util
from appengine_module.chromium_committers import committers
from appengine_module.chromium_committers import ep_api
from appengine_module.chromium_committers import hmac_util


TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), 'templates')
JINJA2_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    autoescape=True,
    extensions=['jinja2.ext.autoescape'])


class MainPageHandler(webapp2.RequestHandler):

  def get(self):
    """Displays the homepage, with a login url."""
    template = JINJA2_ENVIRONMENT.get_template('index.html')
    template_values = {}

    user = auth_util.User.from_request(self.request)
    template_values['login_url'] = ''
    if not user.is_logged_in:
      template_values['login_url'] = users.create_login_url(dest_url='/')
    template_values['lists'] = committers.get_list_names_for_user(user)

    page = template.render(template_values)
    self.response.write(page)


class ListHandler(webapp2.RequestHandler):

  @hmac_util.CheckHmacAuth
  def get(self, list_name):
    """Displays the list of chromium committers in plain text."""
    user = auth_util.User.from_request(self.request)
    try:
      l = committers.get_list(user, list_name)
    except committers.InvalidList as e:
      logging.warning('User requested invalid list: %s', e.message)
      self.abort(404)
    except committers.AuthorizationError as e:
      # Technically should be 403, but use 404 to avoid exposing list names.
      logging.warning('Request not authorized: %s', e.message)
      self.abort(404)
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.write('\n'.join(sorted(l.emails)))


class UpdateHandler(webapp2.RequestHandler):

  @hmac_util.CheckHmacAuth
  @auth_util.RequireAuth
  def post(self, list_name):
    """Updates the list of committers from the POST data recieved."""
    user = auth_util.User.from_request(self.request)
    email_json = base64.b64decode(self.request.get('committers'))
    emails = json.loads(email_json)

    # Throws committers.AuthorizationError if not HMAC authenticated, but we
    # require that via the decorator.
    committers.put_list(user, list_name, emails)


app = webapp2.WSGIApplication([
    ('/', MainPageHandler),
    ('/lists/([a-zA-Z0-9.@_-]+)', ListHandler),
    ('/update/([a-zA-Z0-9.@_-]+)', UpdateHandler),
    ], debug=True)

ep_server = endpoints.api_server([ep_api.CommittersApi])
