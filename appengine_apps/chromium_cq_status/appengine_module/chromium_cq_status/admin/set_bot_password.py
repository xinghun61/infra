# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from appengine_module.chromium_cq_status.shared import utils
from appengine_module.chromium_cq_status.shared.config import CQ_BOT_PASSWORD_KEY  # pylint: disable=C0301
from appengine_module.chromium_cq_status.model.password import Password

def get(handler): # pragma: no cover
  handler.response.write(open('templates/set_bot_password.html').read())

def post(handler): # pragma: no cover
  password = handler.request.get('password')
  if not password:
    handler.response.write('"password" field missing.')
    return

  Password.get_or_insert(
      CQ_BOT_PASSWORD_KEY,
      sha1=utils.password_sha1(password)
  ).put()
  handler.response.write('Bot password successfully updated.')
