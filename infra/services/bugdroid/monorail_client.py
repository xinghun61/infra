# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import apiclient.discovery
import apiclient.http
import httplib2
import json
import logging
import oauth2client.client
import ssl
import time

from apiclient.errors import HttpError
from oauth2client.client import OAuth2Credentials
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from oauth2client.tools import run

from infra_libs import httplib2_utils

MONORAIL_PROD_URL = ('https://monorail-prod.appspot.com/_ah/api/discovery/'
                     'v1/apis/{api}/{apiVersion}/rest')


def build_client(discovery_url, request_builder, api_name, api_version):
  # This occassionally hits a 503 "Backend Error". Hopefully a simple retry
  # can recover.
  tries_left = 5
  tries_wait = 10
  while tries_left:
    tries_left -= 1
    try:
      client = apiclient.discovery.build(
          api_name, api_version,
          discoveryServiceUrl=discovery_url,
          requestBuilder=request_builder)
      break
    except HttpError as e:
      if tries_left:
        logging.error(
            'apiclient.discovery.build() failed for %s: %s', api_name, e)
        logging.error(
            'Retrying apiclient.discovery.build() in %s seconds.',
            tries_wait)
        time.sleep(tries_wait)
      else:
        logging.exception(
            'apiclient.discovery.build() failed for %s too many times.',
            api_name)
        raise e
  return client


class SSLErrorLoggingHttp(object):
  """A httplib2.Http object that logs ssl.SSLError.  For crbug/625036."""

  def __init__(self, http):
    """
    Args:
      http: an httplib2.Http instance
    """
    self._http = http

  def request(self, *args, **kwargs):
    try:
      return self._http.request(*args, **kwargs)
    except ssl.SSLError:
      logging.exception('SSL error in Monorail API request.  Will be retried')
      raise

  def __getattr__(self, name):
    return getattr(self._http, name)

  def __setattr__(self, name, value):
    if name == '_http':
      self.__dict__[name] = value
    else:
      setattr(self._http, name, value)


class MonorailClient(object):

  def __init__(self, credential_store, client=None):
    self._credentials = None

    if client is None:  # pragma: no cover
      with open(credential_store) as data_file:
        creds_data = json.load(data_file)

      self._credentials = OAuth2Credentials(
          None, creds_data['client_id'], creds_data['client_secret'],
          creds_data['refresh_token'], None,
          'https://accounts.google.com/o/oauth2/token',
          'python-issue-tracker-manager/2.0')

      if self._credentials.invalid:
        raise Exception(
            'Failed to create credentials from credential store: %s.' %
            credential_store)

      client = build_client(
          MONORAIL_PROD_URL, self._http_request_builder, 'monorail', 'v1')

    self.client = client

  def _http_request_builder(self, _http, *args, **kwargs):
    http = httplib2_utils.InstrumentedHttp('monorail')
    http = self._credentials.authorize(http)
    http = SSLErrorLoggingHttp(http)
    return apiclient.http.HttpRequest(http, *args, **kwargs)

  def _authenticate(self, storage, service_acct, client_id,
                    client_secret, api_scope):
    flow = OAuth2WebServerFlow(
      client_id=client_id,
      client_secret=client_secret,
      scope=api_scope,
      user_agent='python-issue-tracker-manager/2.0',
      redirect_uri='urn:ietf:wg:oauth:2.0:oob')

    if service_acct:
      if not hasattr(oauth2client.client, 'SignedJwtAssertionCredentials'):
        raise Exception('A version of Python with cryptographic libraries '
                        'built in is necessary to use service accounts.')
      credentials = oauth2client.client.SignedJwtAssertionCredentials(
          client_id, client_secret, scope=api_scope,
          user_agent='python-issue-tracker-manager/2.0')
    else:
      auth_uri = flow.step1_get_authorize_url()
      print 'Open the following URL in your browser:\n'
      print auth_uri + '\n'
      auth_code = raw_input('Enter verification code: ').strip()
      credentials = flow.step2_exchange(auth_code)

    storage.acquire_lock()
    try:
      storage.locked_put(credentials)
    finally:
      storage.release_lock()

    credentials.set_store(storage)
    return credentials

  def update_issue(self, project_name, issue, send_email=True):
    if not issue.dirty:
      return issue

    body = {'id': issue.id, 'updates': {}}
    if issue.labels_added:
      body['updates']['labels'] = list(issue.labels_added)

    if issue.comment:
      body['content'] = issue.comment

    req = self.client.issues().comments().insert(projectId=project_name,
                                                 issueId=issue.id,
                                                 sendEmail=send_email,
                                                 body=body)

    # Hack to investigate crbug/625036.  Replace the content handler inside
    # googleapiclient's HttpRequest with one that also logs the response that
    # causes a UnicodeDecodeError.
    original_postproc = req.postproc
    def request_postproc(resp, content):
      try:
        return original_postproc(resp, content)
      except UnicodeDecodeError:
        logging.debug(
            'Error decoding UTF-8 HTTP response.  Response headers:\n%r\n'
            'Response body:\n%r', resp, content)
        raise
    req.postproc = request_postproc

    req.execute(num_retries=5)

    # Clear the issue comment once it's been saved (shouldn't be re-used)
    issue.comment = ''
    issue.dirty = False
    return issue

  def get_issue(self, project_name, issue_id):
    """Retrieve a set of issues in a project."""
    entry = self.client.issues().get(
        projectId=project_name, issueId=issue_id).execute(num_retries=5)
    return Issue(entry['id'], entry.get('labels', []))


class Issue(object):

  def __init__(self, issue_id, labels):
    self.id = issue_id
    self.comment = ''
    self.labels = labels

    self.labels_added = set()
    self.dirty = False

  def set_comment(self, comment):
    self.comment = comment
    self.dirty = True

  def add_label(self, label):
    if self.has_label(label):
      return

    self.labels.append(label)
    self.labels_added.add(label)
    self.dirty = True

  def remove_label(self, label):
    if not self.has_label(label):
      return

    for l in self.labels:  # pragma: no cover
      if l.lower() == label.lower():
        self.labels.remove(l)
        self.dirty = True
        break

    self.add_label('-%s' % label)

  def has_label(self, value):
    return any(x.lower() == value.lower() for x in self.labels)
