# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file handles serving the list of committers to users."""

__author__ = 'agable@google.com (Aaron Gable)'


import base64
import json
import os

import jinja2
import webapp2

from google.appengine.api import users
from google.appengine.ext import ndb

import auth_util
import constants
import hmac_util
import model


TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), 'templates')
JINJA2_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    autoescape=True,
    extensions=['jinja2.ext.autoescape'])


class MainPageHandler(webapp2.RequestHandler):

  def get(self):
    """Displays the homepage, with a login url."""
    template = JINJA2_ENVIRONMENT.get_template('index.html')
    template_values = {'login_url': users.create_login_url(dest_url='/')}
    page = template.render(template_values)
    self.response.write(page)


class ChromiumHandler(webapp2.RequestHandler):

  @auth_util.CheckUserAuth
  @hmac_util.CheckHmacAuth
  @auth_util.RequireAuth
  def get(self):
    """Displays the list of chromium committers in plain text."""
    committer_list = ndb.Key(model.EmailList, constants.LIST).get()
    emails = committer_list.emails if committer_list else []
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.write('\n'.join(sorted(emails)))


class MappingHandler(webapp2.RequestHandler):

  def get(self):
    """Displays the mapping of chromium to googler email addresses."""
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('Not yet implemented. Sorry!')


class UpdateHandler(webapp2.RequestHandler):

  @hmac_util.CheckHmacAuth
  @auth_util.RequireAuth
  def post(self):
    """Updates the list of committers from the POST data recieved."""
    emails = base64.b64decode(self.request.get('committers'))
    email_list = json.loads(emails)
    committer_list = model.EmailList(id=constants.LIST, emails=email_list)
    committer_list.put()


app = webapp2.WSGIApplication([
    ('/', MainPageHandler),
    ('/chromium', ChromiumHandler),
    ('/mapping', MappingHandler),
    ('/update', UpdateHandler),
  ], debug=True)
