import apiclient
import datetime
import httplib2
import json
import logging
import urllib
import utils
import webapp2

from components import auth
from google.appengine.api import app_identity
from google.appengine.api import urlfetch
from googleapiclient.errors import HttpError
from oauth2client.client import GoogleCredentials

LOGGER = logging.getLogger(__name__)

DISCOVERY_URL = (
    'https://monorail-prod.appspot.com/_ah/api/discovery/v1/apis/'
    '{api}/{apiVersion}/rest')

class TrooperQueueHandler(auth.AuthenticatingHandler): # pragma: no cover
  xsrf_token_enforce_on = []
  xsrf_token_request_param = None

  def __init__(self, request, response):
    self.initialize(request, response)
    credentials = GoogleCredentials.get_application_default()
    self.monorail = apiclient.discovery.build(
        'monorail', 'v1',
        discoveryServiceUrl=DISCOVERY_URL,
        credentials=credentials)

  @auth.public
  def get(self):
    alerts = []

    if not utils.is_trooper_or_admin():
      LOGGER.warn('unauthorized request for trooper queue')
      self.response.write('{}')
      return

    try:
      response = self.monorail.issues().list(projectId='chromium', can='open',
          q='Infra=Troopers -has:owner').execute(num_retries=5)
      alerts = self.make_alerts(response, 'UNOWNED: ')

      response = self.monorail.issues().list(projectId='chromium', can='open',
          q='Infra=Troopers has:owner').execute(num_retries=5)
      alerts.extend(self.make_alerts(response))

    except apiclient.errors.HttpError as e:
      LOGGER.error(e)
      self.response.write('{}')
      return
    except  httplib2.HttpLib2Error as e:
      LOGGER.error(e)
      self.response.write('{}')
      return

    self.response.write(json.dumps({'alerts': alerts}))

  def make_alerts(self, response, note=''):
    alerts = []
    for issue in response.get('items', []):
      alerts.append({
          'key': 'crbug_issue_id:%d' % issue['id'],
          'title': '%s%s' % (note, issue['title']),
          'body': '',
          'links': [{
              'title': 'crbug.com/%d' % issue['id'],
              'href': 'https://crbug.com/%s' % issue['id']
          }],
          'start_time': issue['published'],
          'time': datetime.datetime.utcnow().isoformat() + 'Z',
          'type': 'crbug'
      })

    return alerts

app = webapp2.WSGIApplication([
    ('/trooper-queue', TrooperQueueHandler),
])
