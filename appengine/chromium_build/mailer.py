import hashlib
import hmac
import json
import logging
import time

from google.appengine.api import app_identity
from google.appengine.api import mail
from google.appengine.ext import ndb
from google.appengine.api import oauth
import webapp2
from webapp2_extras import jinja2

import gatekeeper_mailer
import gae_ts_mon


GATEKEEPER_SERVICE_ACCOUNT_EMAILS = (
    'gatekeeper@chromium-build.iam.gserviceaccount.com',
    'gatekeeper-builder@chops-service-accounts.iam.gserviceaccount.com',
    'infra-internal-gatekeeper@chops-service-accounts.iam.gserviceaccount.com')


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


def _get_user_email():
  """Returns the email of the oauth client user."""
  try:
    user = oauth.get_current_user([
        "https://www.googleapis.com/auth/userinfo.email"])
  except (oauth.OAuthRequestError, oauth.OAuthServiceFailureError):
    user = None
  return user.email() if user else None


class Email(BaseHandler):
  @staticmethod
  def _verify_json(build_data):
    """Verifies that the submitted JSON contains all the proper fields."""
    fields = ['waterfall_url',
              'build_url',
              'project_name',
              'builderName',
              'unsatisfied',
              'revisions',
              'blamelist',
              'result',
              'number',
              'reason',
              'recipients']

    for field in fields:
      if field not in build_data:
        logging.error('build_data did not contain field %s' % field)
        return False

    return True

  def post(self):
    email = _get_user_email()
    logging.info('current user email is %s', email)
    if email not in GATEKEEPER_SERVICE_ACCOUNT_EMAILS:
      self.response.out.write('user %r is not authorized' % email)
      logging.warning('user %r is not authorized' % email)
      self.error(403)
      return

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

    subject_template = build_data.get('subject_template')
    status_header = build_data.get('status_header')

    template = gatekeeper_mailer.MailTemplate(build_data['waterfall_url'],
                                              build_data['build_url'],
                                              build_data['project_name'],
                                              from_addr,
                                              subject=subject_template,
                                              status_header=status_header)


    text_content, html_content, subject = template.genMessageContent(build_data)

    sentries = ['gatekeeper-ng@chromium-gatekeeper-sentry.appspotmail.com']

    recipients = list(set(build_data['recipients'] + sentries))

    message = mail.EmailMessage(sender=from_addr,
                                subject=subject,
                                to=recipients,
                                body=text_content,
                                html=html_content)
    logging.info('sending email to %s', ', '.join(recipients))
    logging.info('sending from %s', from_addr)
    logging.info('subject is %s', subject)
    message.send()
    self.response.out.write('email sent')


app = webapp2.WSGIApplication([('/mailer/', MainPage),
                               ('/mailer/email', Email)],
                              debug=True)
gae_ts_mon.initialize(app)
