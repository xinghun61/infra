# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import contextlib
import datetime
import datetime_encoder
import json
import logging
import os
import sys
import webapp2
import zlib

import cloudstorage as gcs

from google.appengine.api import app_identity
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.datastore import datastore_query
from google.appengine.ext import ndb

from components import auth


class UserPrefs(ndb.Model):
  user_id = ndb.StringProperty()
  use_uberchromegw = ndb.BooleanProperty()
  use_new_windows = ndb.BooleanProperty()

class UserPrefsHandler(auth.AuthenticatingHandler):

  @auth.public
  def get(self):
    # Is a get even necessary?  This should probably just be loaded with
    # the inital page contents.
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    self.response.headers['Content-Type'] = 'application/json'
    data = {
      'xsrf_token': self.generate_xsrf_token(),
      'login_url': users.create_login_url('/prefs'),
    }

    user = users.get_current_user()
    if user:
      data['user'] = user.nickname()
      data['logout_url'] = users.create_logout_url('/prefs')

      prefsQry = UserPrefs.query(UserPrefs.user_id == user.user_id()).iter()
      if prefsQry.has_next():
        prefs = prefsQry.next()
        data['prefs'] = {
          'use_uberchromegw': prefs.use_uberchromegw,
          'use_new_windows': prefs.use_new_windows
        }

    self.response.write(json.dumps(data))

  @auth.require(users.get_current_user)
  def post(self):
    try:
      prefs = json.loads(self.request.get('prefs'))
    except ValueError:
      msg = 'content field was not JSON'
      self.response.set_status(400, msg)
      logging.warn(msg)
      return

    user = users.get_current_user()
    user_prefs = UserPrefs(user_id = user.user_id())

    prefs_list = UserPrefs.query(UserPrefs.user_id == user.user_id()).fetch(1)
    if prefs_list:
      prefs = prefs_list[0]

    user_prefs.use_uberchromegw = prefs['use_uberchromegw']
    user_prefs.use_new_windows = prefs['use_new_windows']
    user_prefs.put()

app = webapp2.WSGIApplication([
    ('/api/v1/prefs', UserPrefsHandler),
])
