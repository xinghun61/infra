# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides API wrapper for the codesite issue tracker"""

import httplib2

from endpoints_client import endpoints
from monorail_api.issue import Issue
from monorail_api.comment import Comment


DISCOVERY_URL = ('https://monorail%s.appspot.com/_ah/api/discovery/v1/apis/'
                 '{api}/{apiVersion}/rest')


class IssueTrackerAPI(object):
  CAN_ALL = 'all'

  """A wrapper around the issue tracker api."""
  def __init__(self, project_name, use_staging=False):
    self.project_name = project_name

    if use_staging:
      discovery_url = DISCOVERY_URL % '-staging'
    else:
      discovery_url = DISCOVERY_URL % '-prod'

    self.client = endpoints.build_client(
        'monorail', 'v1', discovery_url, http=httplib2.Http(timeout=60))

  def create(self, issue, send_email=True):
    body = {}
    assert issue.summary
    body['summary'] = issue.summary
    if issue.description:
      body['description'] = issue.description
    if issue.status:
      body['status'] = issue.status
    if issue.owner:
      body['owner'] = {'name': issue.owner}
    if issue.labels:
      body['labels'] = issue.labels
    if issue.components:
      body['components'] = issue.components
    if issue.cc:
      body['cc'] = [{'name': user} for user in issue.cc]
    request = self.client.issues().insert(
        projectId=self.project_name, sendEmail=send_email, body=body)
    tmp = endpoints.retry_request(request)
    issue.id = tmp['id']
    issue.setClean()
    return issue

  def update(self, issue, comment=None, send_email=True):
    if not issue.dirty and not comment:
      return issue

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
      updates['labels'].extend('-%s' % label for label in issue.labels.removed)
    if issue.components.isChanged():
      updates['components'] = list(issue.components.added)
      updates['components'].extend(
          '-%s' % comp for comp in issue.components.removed)
    if issue.cc.isChanged():
      updates['cc'] = list(issue.cc.added)
      updates['cc'].extend('-%s' % cc for cc in issue.cc.removed)

    body = {'id': issue.id,
            'updates': updates}

    if comment:
      body['content'] = comment

    request = self.client.issues().comments().insert(
        projectId=self.project_name, issueId=issue.id, sendEmail=send_email,
        body=body)
    endpoints.retry_request(request)

    if issue.owner == '----':
      issue.owner = ''

    issue.setClean()
    return issue

  def getCommentCount(self, issue_id):
    request = self.client.issues().comments().list(
        projectId=self.project_name, issueId=issue_id, startIndex=1,
        maxResults=0)
    feed = endpoints.retry_request(request)
    return feed.get('totalResults', '0')

  def getComments(self, issue_id):
    rtn = []

    request = self.client.issues().comments().list(
        projectId=self.project_name, issueId=issue_id)
    feed = endpoints.retry_request(request)
    rtn.extend([Comment(entry) for entry in feed['items']])
    total_results = int(feed['totalResults'])

    while len(rtn) < total_results:
      request = self.client.issues().comments().list(
          projectId=self.project_name, issueId=issue_id, startIndex=len(rtn))
      feed = endpoints.retry_request(request)
      rtn.extend([Comment(entry) for entry in feed['items']])

    return rtn

  def postComment(self, issue_id, comment, send_email=True):
    request = self.client.issues().comments().insert(
      projectId=self.project_name, issueId=issue_id, sendEmail=send_email,
      body={'content': comment})
    endpoints.retry_request(request)

  def getIssue(self, issue_id, project_id=None):
    """Retrieve a set of issues in a project."""
    if project_id is None:
      project_id = self.project_name
    request = self.client.issues().get(projectId=project_id, issueId=issue_id)
    entry = endpoints.retry_request(request)
    return Issue(entry)
