# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import apiclient.discovery
import datetime
import httplib2
import json
import logging
import oauth2client.client
import time

from apiclient.errors import HttpError
from oauth2client.client import OAuth2Credentials
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from oauth2client.tools import run

from infra.services.bugdroid.Comment import Comment
from infra.services.bugdroid.Issue import changelist
from infra.services.bugdroid.Issue import Issue2
from infra_libs import httplib2_utils


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

MONORAIL_PROD_URL = ('https://monorail-prod.appspot.com/_ah/api/discovery/'
                     'v1/apis/{api}/{apiVersion}/rest')


def convertEntryToComment(entry):
  comment = Comment()
  comment.author = entry['author']['name']
  comment.comment = entry['content']
  comment.created = parseDateTime(entry['published'])
  comment.id = entry['id']

  if 'updates' in entry and entry['updates']:
    comment.cc = changelist([e for e in entry['updates'].get('cc', [])])
    comment.labels = changelist([e for e in entry['updates'].get('labels', [])])
    comment.owner = entry['updates'].get('owner', None)
    comment.status = entry['updates'].get('status', None)
    comment.summary = entry['updates'].get('summary', None)

    comment.merged_into = [e for e in entry['updates'].get('mergedInto', [])]
    comment.blocked_on = [e for e in entry['updates'].get('blockedOn', [])]

  return comment


def parseDateTime(dt_str):
  dt, _, us = dt_str.partition(".")
  dt = datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
  if us:
    us = int(us.rstrip("Z"), 10)
    return dt + datetime.timedelta(microseconds=us)
  else:
    return dt


def convertEntryToIssue(entry, itm, old_issue=None):
  if old_issue:
    issue = old_issue
  else:
    issue = Issue2()
  issue.id = entry['id']

  issue.blocked_on = [e['issueId'] for e in entry.get('blockedOn', [])]
  issue.blocking =  [e['issueId'] for e in entry.get('blocking', [])]

  if entry.get('mergedInto', []):
    issue.merged_into = [entry['mergedInto']['issueId']]

  issue.created = parseDateTime(entry['published'])
  issue.updated = parseDateTime(entry['updated'])

  if entry.get('closed',[]):
    issue.closed = parseDateTime(entry.get('closed',[]))

  issue.summary = entry['summary'] #was title

  issue.reporter = entry['author']['name']
  if entry.get('owner', []):
    issue.owner = entry['owner']['name']

  if entry.get('owner', []):
    issue.owner = entry['owner']['name']
  if entry.get('status', []):
    issue.status = entry['status']

  issue.stars = entry['stars']
  issue.open = entry['state'] == 'open'
  issue.labels = changelist(entry.get('labels', []))
  issue.cc = changelist([e['name'] for e in entry.get('cc', [])])
  issue.comments = None

  issue.dirty = False
  issue.new = False
  issue.itm = itm
  return issue


def build_client(discovery_url, http, api_name, api_version):
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
          http=http)
      break
    except HttpError as e:
      if tries_left:
        LOGGER.error(
            'apiclient.discovery.build() failed for %s: %s', api_name, e)
        LOGGER.error(
            'Retrying apiclient.discovery.build() in %s seconds.',
            tries_wait)
        time.sleep(tries_wait)
      else:
        LOGGER.exception(
            'apiclient.discovery.build() failed for %s too many times.',
            api_name)
        raise e
  return client


class IssueTrackerManager(object):
  '''
  classdocs
  '''
  CAN_ALL = 'all'
  CAN_OPEN = 'open'
  CAN_MY_OPEN_BUGS = 'owned'
  CAN_REPORTED_BY_ME = 'reported'
  CAN_STARRED_BY_ME = 'starred'
  CAN_NEW = 'new'
  CAN_VERIFY = 'to-verify'

  def __init__(self, client_id, client_secret, project_name,
               credential_store='phosting.dat', service_acct=False):
    '''
     Constructor
    '''
    self.project_name = project_name
    self._empty_owner_value = '----'

    with open(credential_store) as data_file:    
      creds_data = json.load(data_file)

    credentials = OAuth2Credentials(
        None, creds_data['client_id'], creds_data['client_secret'],
        creds_data['refresh_token'], None,
        'https://accounts.google.com/o/oauth2/token',
        'python-issue-tracker-manager/2.0')

    if credentials is None or credentials.invalid == True:
      api_scope = 'https://www.googleapis.com/auth/projecthosting'
      credentials = self._authenticate(storage=None,
                                       service_acct=service_acct,
                                       client_id=client_id,
                                       client_secret=client_secret,
                                       api_scope=api_scope)

    http = httplib2.Http()
    http = credentials.authorize(http)

    discovery_url = ('https://www.googleapis.com/discovery/v1/apis/{api}/'
                     '{apiVersion}/rest')
    self.client = build_client(discovery_url, http, 'projecthosting', 'v2')

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

  def save(self, issue, send_email=True):
    if issue.new:
      return self._create(issue)
    else:
      return self._update(issue, send_email)

  def _create(self, issue, send_email=True):
    cc = [{'name': user} for user in issue.cc]
    tmp = self.client.issues().insert(projectId=self.project_name,
                                      sendEmail=send_email,
                                      body={'summary': issue.summary,
                                            'description': issue.body,
                                            'status': issue.status,
                                            'owner': {'name': issue.owner},
                                            'labels': issue.labels,
                                            'cc': cc}).execute(num_retries=5)
    issue.id = int(tmp['id']) # i think already int
    issue.dirty = False
    issue.new = False
    return issue

  def _update(self, issue, send_email=True):
    if not issue.dirty:
      return issue
    if not issue.owner:
      # workaround for existing bug:
      # https://code.google.com/a/google.com/p/codesite/issues/detail?id=115
      issue.owner = self._empty_owner_value

    updates = {}
    if 'summary' in issue.changed:
      updates['summary'] = issue.summary
    if 'status' in issue.changed:
      updates['status'] = issue.status
    if 'owner' in issue.changed:
      updates['owner'] = issue.owner
    if 'blocked_on' in issue.changed:
      updates['blockedOn'] = issue.blocked_on
    if issue.labels.isChanged():
      updates['labels'] = list(issue.labels.added)
    if issue.cc.isChanged():
      #TODO figure out what this logic should be, I have yet to make this work
      updates['cc'] = list(issue.cc.added)

    body = {'id': issue.id,
            'updates': updates}

    if 'comment' in issue.changed:
      body['content'] = issue.comment

    self.client.issues().comments().insert(projectId=self.project_name,
                                           issueId=issue.id,
                                           sendEmail=send_email,
                                           body=body).execute(num_retries=5)


    if issue.owner == self._empty_owner_value:
      issue.owner = ''

    #Clear the issue comment once it's been saved (shouldn't be re-used)
    issue.comment = ''
    issue.dirty = False
    return issue

  def addComment(self, issue_id, comment, send_email=True):
    issue = self.getIssue(issue_id)
    issue.comment = comment
    self.save(issue, send_email)

  def getCommentCount(self, issue_id):
    feed = self.client.issues().comments().list(
        projectId=self.project_name,
        issueId=issue_id,
        startIndex=1,
        maxResults=0).execute(num_retries=5)
    return feed.get('totalResults', '0')

  def getComments(self, issue_id):
    rtn = []

    comments_feed = self.client.issues().comments().list(
        projectId=self.project_name,issueId=issue_id).execute(num_retries=5)
    rtn.extend(
        [convertEntryToComment(entry) for entry in comments_feed['items']])
    total_results = comments_feed['totalResults']
    if total_results:
      total_results = comments_feed['totalResults']
    else:
      return rtn

    while len(rtn) < total_results:
      comments_feed = self.client.issues().comments().list(
          projectId=self.project_name, issueId=issue_id,
          startIndex=len(rtn)).execute(num_retries=5)
      rtn.extend(
          [convertEntryToComment(entry) for entry in comments_feed['items']])

    return rtn

  def getFirstComment(self, issue_id):
    feed = self.client.issues().comments().list(
        projectId=self.project_name,
        issueId=issue_id,
        startIndex=0,
        maxResults=1).execute(num_retries=5)
    if 'items' in feed:
      return convertEntryToComment(feed['items'][0])

  def getLastComment(self, issue_id):
    total_results = self.getCommentCount(issue_id)
    feed = self.client.issues().comments().list( 
        projectId=self.project_name,
        issueId=issue_id,
        startIndex=total_results-1,
        maxResults=1).execute(num_retries=5)
    if 'items' in feed:
      return convertEntryToComment(feed['items'][0])
    return None


  def getIssue(self, issue_id):
    """Retrieve a set of issues in a project."""
    entry = self.client.issues().get(
        projectId=self.project_name, issueId=issue_id).execute(num_retries=5)
    return convertEntryToIssue(entry, self)

  def refresh(self, issue):
    if issue and not issue.new:
      entry = self.client.issues().get(
          projectId=self.project_name, issueId=issue.id).execute(num_retries=5)
      return convertEntryToIssue(entry, self, old_issue=issue)

    return issue

  def getAllIssues(self):
    feed = self.client.issues().list(projectId=self.project_name).execute(
        num_retries=5)
    return [convertEntryToIssue(entry, self) for entry in feed['items']]

  def getIssuesCount(self, query_str, can=CAN_ALL):
    feed = self.client.issues().list(can=can,
                                     projectId=self.project_name,
                                     q=query_str,
                                     startIndex=0,
                                     maxResults=0).execute(num_retries=5)
    total_results = feed.get('totalResults', '')
    if total_results:
      return int(total_results)
    else:
      return 0

  def getIssues(self, query, can=CAN_ALL, max_results = 1000):
    rtn = []
    count = 0
    block_count = 0
    while True:
      result, total = self.getIssuesUsingQuery(
          query, can, max_results=max_results, start_index=count)
      count += len(result)
      #Ugly hack, because the issue tracker is omitting results randomly
      block_count += max_results
      rtn += result

      if block_count > total:
        break
    return rtn


  def getIssuesUsingQuery(self, query_str, can=CAN_ALL, max_results = 1000,
                          start_index=0):
    """Retrieve a set of issues in a project."""
    feed = self.client.issues().list(projectId=self.project_name,
                                     q=query_str,
                                     startIndex=start_index,
                                     maxResults=max_results,
                                     can=can).execute(num_retries=5)
    if 'items' in feed and len(feed['items']) > 0:
      return ([convertEntryToIssue(entry, self) for entry in feed['items']],
              feed['totalResults'])
    else:
      return [], 0


class MonorailIssueTrackerManager(IssueTrackerManager):

  def __init__(self, project_name, credential_store='monorail.dat',
               client_id="", client_secret="", service_acct=False,
               discovery_url=MONORAIL_PROD_URL):
    '''
     Constructor
    '''
    self.project_name = project_name
    self._empty_owner_value = ''

    with open(credential_store) as data_file:    
      creds_data = json.load(data_file)

    credentials = OAuth2Credentials(
        None, creds_data['client_id'], creds_data['client_secret'],
        creds_data['refresh_token'], None,
        'https://accounts.google.com/o/oauth2/token',
        'python-issue-tracker-manager/2.0')

    if credentials is None or credentials.invalid == True:
      if not client_id or not client_secret:
        raise Exception(
            'Failed to create credentials from credential store: %s. '
            'To authenticate and write fresh credentials to the store, '
            'create MonorailIssueTrackerManager with valid |client_id| '
            'and |client_secret| arguments.' % credential_store)
      api_scope = 'https://www.googleapis.com/auth/userinfo.email'
      credentials = self._authenticate(storage=None,
                                       service_acct=service_acct,
                                       client_id=client_id,
                                       client_secret=client_secret,
                                       api_scope=api_scope)

    http = httplib2_utils.InstrumentedHttp('monorail:%s' % self.project_name)
    http = credentials.authorize(http)

    self.client = build_client(discovery_url, http, 'monorail', 'v1')
