# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This app expects periodic emails, and pages when they stop being received."""

import logging
import time
import webapp2

from appengine_module.heartbeat import models
from google.appengine.ext.ndb import Key
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler


class MailHandler(InboundMailHandler): # pragma: no cover
  """Class for handling incoming mail."""

  def receive(self, mail_message):
    """Handle incoming emails.

    Args:
      mail_message: An InboundEmailMessage instance.
    """
    # Read from the config to determine if this email is important.
    config = models.Config.query(
      models.Config.sender == mail_message.sender).get()

    if config is None:
      self.log('Disregarding email from', mail_message.sender)
      return

    # Read the last known heartbeat. See below for why it is retrieved this way.
    heartbeat = Key(
      models.MostRecentHeartbeat, '%s-latest' % config.sender).get()

    if heartbeat is None:
      self.log('Received very first email from', config.sender)
    else:
      self.log('Received new email from', heartbeat.sender)

    # Write this heartbeat to the datastore.
    models.Heartbeat(sender=config.sender, timestamp=mail_message.date).put()

    # Write this heartbeat to the datastore again with a known key, for fast
    # retrieval of the latest heartbeat. We use a different class so that this
    # doesn't duplicate the heartbeats in the datastore.
    models.MostRecentHeartBeat(
      key='%s-latest' % config.sender,
      sender=config.sender,
      timestamp=mail_message.date,
    ).put()

  @staticmethod
  def log(*msg):
    logging.info(time.strftime('[%D %H:%M:%S]', time.localtime()), *msg)


class RequestHandler(webapp2.RequestHandler):
  """Class for handling HTTP requests for this app."""

  def get(self):
    self.response.write('hello, world.')


app = webapp2.WSGIApplication([
  ('/', RequestHandler),
  MailHandler.mapping(),
])
