# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This app expects periodic emails, and pages when they stop being received."""

from datetime import datetime
import logging
import math
import time
import webapp2

from appengine_module.heartbeat import models
from google.appengine.api import app_identity
from google.appengine.api import mail
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler


VERSION = '0.3'


class CronWorker(webapp2.RequestHandler):
  """Class for checking if heartbeat emails have arrived."""

  @staticmethod
  def get():
    """Ensure heartbeat emails are up to date."""
    for config in models.Config.query().iter():
      # Read the last known heartbeat for this config. See MailHandler.receive
      # for why it is retrieved this way.
      heartbeat = models.MostRecentHeartbeat.get_by_id(
        '%s-latest' % config.sender)

      email_message = ''

      if heartbeat is None:
        email_message = 'No emails have been received from %s.' % config.sender
      else:
        heartbeat_delta = (
          datetime.now() - heartbeat.timestamp).total_seconds() / 60

        if heartbeat_delta > config.timeout:
          email_message = 'No email received from %s in %s minutes.' % (
            config.sender, heartbeat_delta)

      if email_message:
        # Read the last known alert for this instance of a missed email. See
        # below for why it is retrieved this way.
        alert = models.MostRecentAlert.get_by_id(
          '%s-latest' % config.sender)

        if alert is not None and alert.total > 0:
          # This means we already alerted for this particular problem. Check
          # how many times we've alerted as well as the most recent time to
          # determine if we should alert again. Here we exponentially back off
          # to a max of one alert email per hour.
          alert_delta = (datetime.now() - alert.timestamp).total_seconds() / 60

          # If we've already sent at least one email before, then the logic is
          # as follows: wait 2^(n-1) minutes, where n is the number of emails
          # we've already sent, to a maximum of 60 minutes. e.g. If we've sent
          # 1 email, then wait 2^0 = 1 minute, if we've sent 2 emails, then
          # wait 2^1 = 2 minutes, if we've sent 3 emails, then wait 2^2 = 4
          # minutes, and if it's been at least an hour, email right away.
          #
          # If delta >= 2^(n-1) then email.
          # => If log_2(delta) >= n - 1 then email.
          # => If log_2(delta) < n - 1 then don't email.
          if alert_delta < 60 and math.log(alert_delta, 2) < alert.total - 1:
            # It's been an insufficient number of minutes since the last alert,
            # so move on to the next config.
            continue

        # At this point there was either no previous alert, or the most recent
        # alert was long enough ago. Either way, send an alert.
        mail.send_mail(
          body='\n'.join([
            email_message,
            'Emails were expected every %s minutes.' % config.timeout,
            # For testing, we ignore the intended recipients. Include them in
            # the email just so we know that they are being properly parsed.
            'Watchlist: %s.' % ', '.join(config.watchlist),
          ]),
          sender='alerts+noreply@%s.appspotmail.com' % (
            app_identity.get_application_id()),
          subject='OH SHIT',
          to=[
            # For testing we ignore the intended recipients.
            'smut@google.com',
            'stip@google.com',
          ],
        )

        # Write this alert to the datastore.
        models.Alert(
          sender=config.sender,
          total=1 if alert is None else alert.total + 1,
        ).put()

      if not email_message:
        # No alert was sent, reset the exponential backoff.
        new_total = 0
      elif alert is None:
        # We just sent the first alert.
        new_total = 1
      else:
        # We've sent one more alert.
        new_total = alert.total + 1

      # Write this alert to the datastore again with a known ID, for fast
      # retrieval of the latest alert. We use a different class so that this
      # doesn't duplicate the alerts in the datastore.
      models.MostRecentAlert(
        id='%s-latest' % config.sender,
        sender=config.sender,
        total=new_total,
      ).put()


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
    heartbeat = models.MostRecentHeartbeat.get_by_id(
      '%s-latest' % config.sender)

    if heartbeat is None:
      self.log('Received very first email from', config.sender)
    else:
      self.log('Received new email from', heartbeat.sender)

    # Write this heartbeat to the datastore.
    models.Heartbeat(sender=config.sender).put()

    # Write this heartbeat to the datastore again with a known ID, for fast
    # retrieval of the latest heartbeat. We use a different class so that this
    # doesn't duplicate the heartbeats in the datastore.
    models.MostRecentHeartbeat(
      id='%s-latest' % config.sender,
      sender=config.sender,
    ).put()

  @staticmethod
  def log(*components):
    """Log a message with logging level INFO.

    Args:
      components: The components of the message.
    """
    timestamp = time.strftime('%D %H:%M:%S')
    message = ' '.join(str(component) for component in components)
    logging.info('[%s]: %s' % (timestamp, message))


class RequestHandler(webapp2.RequestHandler):
  """Class for handling HTTP requests for this app."""

  def get(self):
    self.response.write('v%s\n\n' % VERSION)


app = webapp2.WSGIApplication([
  ('/cron', CronWorker),
  MailHandler.mapping(),
  ('/', RequestHandler),
])
