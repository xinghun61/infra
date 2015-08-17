# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import cgi
import datetime
import json
import logging
import os
import sys
import time
import utils
import webapp2
import zlib


from google.appengine.api import app_identity
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import ndb


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'components', 'third_party'))

from components import auth
from components import template


LOGGER = logging.getLogger(__name__)


class BannerMessage(ndb.Model):
  type = ndb.StringProperty()
  content = ndb.StringProperty()
  date = ndb.DateTimeProperty(auto_now_add=True)
  who = ndb.StringProperty()
  active = ndb.BooleanProperty()

  @staticmethod
  def get_last_datastore(msg_type):
    last_query = BannerMessage.query(
        ancestor=ndb.Key('BannerMessageRoot','0')).filter(
          BannerMessage.type == msg_type)
    return last_query.order(-BannerMessage.date).get()

  def to_json_data(self):
    data = {}
    data['message'] = self.content
    data['date'] = calendar.timegm(self.date.timetuple())
    data['who'] = self.who
    return data



class BannerMessageHandler(webapp2.RequestHandler):

  MSG_TYPE = 'banner-msg'

  def set_json_headers(self):
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    self.response.headers['Content-Type'] = 'application/json'

  def send_json_data(self, data):
    self.set_json_headers()
    self.response.write(
        json.dumps(data, cls=utils.DateTimeEncoder, indent=1))

  def get_from_datastore(self, msg_type):
    last_entry = BannerMessage.get_last_datastore(msg_type)
    if last_entry and last_entry.active:
      data = last_entry.to_json_data()
      memcache.set(msg_type, data)

      self.send_json_data(data)
      return True
    return False

  def get_from_memcache(self, memcache_key):
    data = memcache.get(memcache_key)
    if data:
      self.send_json_data(data)
      return True
    return False

  def get_msg(self, msg_type):
    if not self.get_from_memcache(msg_type):
      if not self.get_from_datastore(msg_type):
        self.send_json_data({})

  def get(self):
    self.get_msg(BannerMessageHandler.MSG_TYPE)


class BannerMessageFormHandler(auth.AuthenticatingHandler):

  @auth.autologin
  @auth.require(utils.is_trooper_or_admin)
  def get(self):
    user = users.get_current_user()
    template_values = {
        'user': user,
        'xsrf_token': self.generate_xsrf_token(),
    }

    latest_msg = BannerMessage.get_last_datastore(
        BannerMessageHandler.MSG_TYPE)

    if latest_msg is not None and latest_msg.active:
      template_values['latest_msg'] = latest_msg

    self.response.write(template.render('som/banner-msg-form.html',
        template_values))

  def store_msg(self, msg_type, msg):
    uid = int(time.time() * 1000000)
    new_entry = BannerMessage(
            key=ndb.Key('BannerMessageRoot', '0', BannerMessage, uid),
            active=True,
            # content is stored unescaped. We sanitize on output, in context.
            content=msg,
            who=users.get_current_user().email(),
            type=msg_type)
    new_entry.put()
    return new_entry

  def deactivate_latest_msg(self, msg_type):
    memcache.delete(msg_type)
    last_entry = BannerMessage.get_last_datastore(msg_type)
    LOGGER.info("last entry: %s" % last_entry)
    if last_entry:
      last_entry.active = False
      last_entry.put()
    else:
      self.response.set_status(500, 'could not find latest message')

  def update_msg(self, msg_type):
    if self.request.get('deactivate'):
      return self.deactivate_latest_msg(BannerMessageHandler.MSG_TYPE)
    else:
      content = self.request.get('content')
      if content:
        return self.store_msg(msg_type, content)

  @auth.require(utils.is_trooper_or_admin)
  def post(self):
    user = users.get_current_user()
    if user:
      msg = self.update_msg(BannerMessageHandler.MSG_TYPE)
      if msg:
        data = msg.to_json_data()
        memcache.set(BannerMessageHandler.MSG_TYPE, data)

      self.redirect('/banner-msg-form')
    else:
      self.response.set_status(401, 'No user auth')

template.bootstrap({'som': os.path.dirname(__file__)})

app = webapp2.WSGIApplication([
    ('/banner-msg', BannerMessageHandler),
    ('/banner-msg-form', BannerMessageFormHandler),
])
