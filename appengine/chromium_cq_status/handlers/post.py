# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from google.appengine.api import users
import webapp2

from shared import utils
from shared.config import (
  AUTO_TAGGED_FIELDS,
  CQ_BOT_PASSWORD_KEY,
  DEFAULT_PROJECT,
)
from shared.parsing import (
  parse_fields,
  parse_key,
  parse_project,
  parse_request,
  parse_tags,
)
from model.password import Password # pylint: disable-msg=E0611
from model.record import Record # pylint: disable-msg=E0611

def update_record(project=DEFAULT_PROJECT,
    key=None, tags=None, fields=None): # pragma: no cover
  tags = tags or []
  fields = fields or {}
  if not key and len(tags) == 0 and len(fields) == 0:
    raise ValueError('Empty record entries disallowed')
  for item in fields:
    if item in AUTO_TAGGED_FIELDS:
      tags.append('%s=%s' % (item, fields[item]))
  record = Record(id=key, namespace=project)
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
        'project': parse_project,
        'key': parse_key,
        'tags': parse_tags,
        'fields': parse_fields,
      }))
    except ValueError, e:
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
    except ValueError, e:
      self.response.write('Invalid packet: %s' % e)
      return

    try:
      for packet in packets:
        update_record(**packet)
    except ValueError, e:
      self.response.write(e)

  def _is_cq_bot(self):
    password = self.request.get('password')
    if not password:
      return False
    sha1 = utils.password_sha1(password)
    return sha1 == Password.get_by_id(CQ_BOT_PASSWORD_KEY).sha1
