# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import traceback

from google.appengine.api import users
import webapp2

from shared import utils
from shared.config import AUTO_TAGGED_FIELDS, CQ_BOT_PASSWORD_KEY
from shared.parsing import (
  parse_fields,
  parse_record_key,
  parse_request,
  parse_strings,
)
from model.password import Password
from model.record import Record

def update_record(key=None, tags=None, fields=None): # pragma: no cover
  tags = tags or []
  fields = fields or {}
  if not key and len(tags) == 0 and len(fields) == 0:
    raise ValueError('Empty record entries disallowed')
  if not 'project' in fields:
    raise ValueError('"Project" field missing')
  for item in fields:
    if item in AUTO_TAGGED_FIELDS:
      tags.append('%s=%s' % (item, fields[item]))
  record = Record(id=key)
  record.tags = list(set(tags))
  record.fields = fields
  record.put()

class Post(webapp2.RequestHandler): # pragma: no cover
  def get(self):
    if not utils.is_valid_user():
      self.redirect(users.create_login_url('/'))
      return

    try:
      update_record(**parse_request(self.request, {
        'key': parse_record_key,
        'tags': parse_strings,
        'fields': parse_fields,
      }))
    except ValueError as e:
      logging.warning(traceback.format_exc())
      self.response.write(e)

  def post(self):
    if not utils.is_valid_user() and not self._is_cq_bot():
      self.response.set_status(403)
      return

    try:
      packets = map(json.loads, self.request.get_all('p'))
      for packet in packets:
        if not isinstance(packet, dict):
          raise ValueError('JSON dictionary expected.')
    except ValueError as e:
      logging.warning(traceback.format_exc())
      self.response.write('Invalid packet: %s' % e)
      return

    try:
      for packet in packets:
        update_record(**utils.filter_dict(packet, ('key', 'tags', 'fields')))
    except ValueError as e:
      logging.warning(traceback.format_exc())
      self.response.write(e)

  def _is_cq_bot(self):
    password = self.request.get('password')
    if not password:
      return False
    sha1 = utils.password_sha1(password)
    return sha1 == Password.get_by_id(CQ_BOT_PASSWORD_KEY).sha1
