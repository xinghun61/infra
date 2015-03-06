# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file handles serving the list of committers to users."""

__author__ = 'agable@google.com (Aaron Gable)'


import base64
import json
import logging
import os

import jinja2
import webapp2

from google.appengine.api import users
from google.appengine.ext import ndb

from appengine_module.chromium_committers import auth_util
from appengine_module.chromium_committers import hmac_util
from appengine_module.chromium_committers import model


TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), 'templates')
JINJA2_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    autoescape=True,
    extensions=['jinja2.ext.autoescape'])
TRUSTED_APP_IDS = [
  'chrome-infra-auth',
  'chrome-infra-auth-dev'
]


class MainPageHandler(webapp2.RequestHandler):

  def get(self):
    """Displays the homepage, with a login url."""
    template = JINJA2_ENVIRONMENT.get_template('index.html')
    template_values = {}

    user = users.get_current_user()
    template_values['login_url'] = ''
    if not user:
      template_values['login_url'] = users.create_login_url(dest_url='/')

    lists = model.EmailList.query().fetch(keys_only=True)
    template_values['lists'] = [l.string_id() for l in lists
                                if auth_util.CheckUserInList(l)]

    page = template.render(template_values)
    self.response.write(page)


class ListHandler(webapp2.RequestHandler):

  @hmac_util.CheckHmacAuth
  def get(self, list_name):
    """Displays the list of chromium committers in plain text."""
    if not list_name:
      logging.warning('Tried to view list with no name.')
      self.abort(404)

    committer_list = ndb.Key(model.EmailList, list_name).get()
    emails = committer_list.emails if committer_list else []
    logging.debug('Fetched emails: %s' % emails)
    if not emails:
      logging.warning('Tried to view nonexistent or empty list.')
      self.abort(404)

    app_id = self.request.headers.get('X-Appengine-Inbound-Appid')
    valid_request = (
        self.request.authenticated == 'hmac' or
        app_id in TRUSTED_APP_IDS or
        auth_util.CheckUserInList(emails)
    )
    if not valid_request:
      # Technically should be 403, but use 404 to avoid exposing list names.
      self.abort(404)
      return

    self.response.headers['Content-Type'] = 'text/plain'
    self.response.write('\n'.join(sorted(emails)))


class UpdateHandler(webapp2.RequestHandler):

  @hmac_util.CheckHmacAuth
  @auth_util.RequireAuth
  def post(self, list_name):
    """Updates the list of committers from the POST data recieved."""
    email_json = base64.b64decode(self.request.get('committers'))
    emails = json.loads(email_json)
    committer_list = model.EmailList(id=list_name, emails=emails)
    committer_list.put()


app = webapp2.WSGIApplication([
    ('/', MainPageHandler),
    ('/lists/([a-zA-Z0-9_-]+)', ListHandler),
    ('/update/([a-zA-Z0-9_-]+)', UpdateHandler),
    ], debug=True)
