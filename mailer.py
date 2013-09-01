import hashlib
import hmac
import json
import logging
import time

from google.appengine.api import app_identity
from google.appengine.api import mail
from google.appengine.ext import ndb
import webapp2
from webapp2_extras import jinja2

import gatekeeper_mailer


class MailerSecret(ndb.Model):
  """Model to represent the shared secret for the mail endpoint."""
  secret = ndb.StringProperty()


class BaseHandler(webapp2.RequestHandler):
  """Provide a cached Jinja environment to each request."""
  @webapp2.cached_property
  def jinja2(self):
    # Returns a Jinja2 renderer cached in the app registry.
    return jinja2.get_jinja2(app=self.app)

  def render_response(self, _template, **context):
    # Renders a template and writes the result to the response.
    rv = self.jinja2.render_template(_template, **context)
    self.response.write(rv)


class MainPage(BaseHandler):
  def get(self):
    context = {'title': 'Chromium Gatekeeper Mailer'}
    self.render_response('main_mailer.html', **context)


class Email(BaseHandler):
  @staticmethod
  def linear_compare(a, b):
    """Scan through the entire string even if a mismatch is detected early.

    This thwarts timing attacks attempting to guess the key one byte at a
    time.
    """
    if len(a) != len(b):
      return False
    result = 0
    for x, y in zip(a, b):
      result |= ord(x) ^ ord(y)
    return result == 0

  @staticmethod
  def _validate_message(message, url, secret):
    """Cryptographically validates the message."""
    mytime = time.time()

    if abs(mytime - message['time']) > 60:
      logging.error('message was rejected due to time')
      return False

    cleaned_url = url.rstrip('/') + '/'
    cleaned_message_url = message['url'].rstrip('/') + '/'

    if cleaned_message_url != cleaned_url:
      logging.error('message URL did not match: %s vs %s', cleaned_message_url,
          cleaned_url)
      return False

    hasher = hmac.new(str(secret), message['message'], hashlib.sha256)
    hasher.update(str(message['time']))
    hasher.update(str(message['salt']))

    client_hash = hasher.hexdigest()

    return Email.linear_compare(client_hash, message['hmac-sha256'])

  @staticmethod
  def _verify_json(build_data):
    """Verifies that the submitted JSON contains all the proper fields."""
    fields = ['waterfall_url',
              'build_url',
              'project_name',
              'builderName',
              'steps',
              'unsatisfied',
              'revisions',
              'blamelist',
              'result',
              'number',
              'changes',
              'reason',
              'recipients']

    for field in fields:
      if field not in build_data:
        logging.error('build_data did not contain field %s' % field)
        return False

    step_fields = ['started',
                   'text',
                   'results',
                   'name',
                   'logs',
                   'urls']

    if not build_data['steps']:
      logging.error('build_data did not contain any steps')
      return False
    for step in build_data['steps']:
      for field in step_fields:
        if field not in step:
          logging.error('build_step did not contain field %s' % field)
          return False

    return True

  def post(self):
    blob = self.request.get('json')
    if not blob:
      self.response.out.write('no json data sent')
      logging.error('error no json sent')
      self.error(400)
      return

    message = {}
    try:
      message = json.loads(blob)
    except ValueError as e:
      self.response.out.write('couldn\'t decode json')
      logging.error('error decoding incoming json: %s' % e)
      self.error(400)
      return

    secret = MailerSecret.get_or_insert('mailer_secret').secret
    if not secret:
      self.response.out.write('unauthorized')
      logging.critical('mailer shared secret has not been set!')
      self.error(500)
      return

    if not self._validate_message(message, self.request.url, secret):
      self.response.out.write('unauthorized')
      logging.error('incoming message did not validate')
      self.error(403)
      return

    try:
      build_data = json.loads(message['message'])
    except ValueError as e:
      self.response.out.write('couldn\'t decode payload json')
      logging.error('error decoding incoming json: %s' % e)
      self.error(400)
      return

    if not self._verify_json(build_data):
      logging.error('error verifying incoming json: %s' % build_data)
      self.response.out.write('json build format is incorrect')
      self.error(400)
      return

    # Emails can only come from the app ID, so we split on '@' here just in
    # case the user specified a full email address.
    from_addr_prefix = build_data.get('from_addr', 'buildbot').split('@')[0]
    from_addr = from_addr_prefix + '@%s.appspotmail.com' % (
        app_identity.get_application_id())

    recipients = ', '.join(build_data['recipients'])

    template = gatekeeper_mailer.MailTemplate(build_data['waterfall_url'],
                                              build_data['build_url'],
                                              build_data['project_name'],
                                              from_addr)


    text_content, html_content, subject = template.genMessageContent(build_data)

    message = mail.EmailMessage(sender=from_addr,
                                subject=subject,
                                #to=recipients,
                                to=['xusydoc@chromium.org'],
                                body=text_content,
                                html=html_content)
    logging.info('sending email to %s', recipients)
    logging.info('sending from %s', from_addr)
    logging.info('subject is %s', subject)
    message.send()
    self.response.out.write('email sent')


app = webapp2.WSGIApplication([('/mailer', MainPage),
                               ('/mailer/email', Email)],
                              debug=True)
