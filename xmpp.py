# Copyright (c) 2009 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Google Talk (XMPP) support."""

from google.appengine.api import xmpp
from google.appengine.ext import webapp


class XMPPHandler(webapp.RequestHandler):
  def post(self):
    message = xmpp.Message(self.request.POST)
    if message.body[0:5].lower() == 'hello':
      message.reply("Greetings!")
