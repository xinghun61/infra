# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from handlers.index import Index # pylint: disable-msg=W0403
from handlers.post import Post # pylint: disable-msg=W0403
from handlers.query import Query # pylint: disable-msg=W0403
from handlers.set_bot_password import SetBotPassword # pylint: disable-msg=W0403

handlers = [
  (r'/', Index),
  (r'/post', Post),
  (r'/query(/.*)?', Query),
  (r'/set-bot-password', SetBotPassword),
]

app = webapp2.WSGIApplication(handlers, debug=True)
