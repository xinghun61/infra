# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import datetime
import json

import httplib2

from apiclient import discovery
from oauth2client import client


PROJECT_HOSTING_SCOPE = 'https://www.googleapis.com/auth/projecthosting'
DISCOVERY_URL = ('https://www.googleapis.com/discovery/v1/apis/{api}/'
                 '{apiVersion}/rest')

# This is needed because there are many labels that have 'Sheriff' in them.
WHITELISTED_LABELS = ['Sheriff-Chromium']
BATCH_SIZE = 10


def _build_crbug_service(crbug_service_account):  # pragma: no cover
  with open(crbug_service_account) as crbug_sa_file:
    service_account = json.load(crbug_sa_file)

  creds = client.SignedJwtAssertionCredentials(
      service_account['client_email'], service_account['private_key'],
      PROJECT_HOSTING_SCOPE)
  http = creds.authorize(httplib2.Http())
  return discovery.build('project_hosting', 'v2',
                         discoveryServiceUrl=DISCOVERY_URL, http=http)


def _list_issues(crbug_service_account):
  service = _build_crbug_service(crbug_service_account)
  issues = []
  seen_issue_ids = set()
  for whitelisted_label in WHITELISTED_LABELS:
    start_index = 1
    while True:
      request = service.issues.list(projectId='chromium',
                                    body={'label': whitelisted_label,
                                          'startIndex': start_index,
                                          'maxResults': BATCH_SIZE,
                                          'can': 'open'})
      response = request.execute(num_retries=5)
  
      # Issue Tracker may omit certain issues occasionally, so counting whether
      # they add up to 'totalResults' in response is not relaible. However, we
      # can use the fact that 'items' is not present in response if we try to
      # list issues starting from an index beyond totalResults.
      if not response.get('items'):
        break
  
      # Here we increment start_index by BATCH_SIZE rather then by the actual
      # number of returned issues in 'items' because as described above, issue
      # tracker may omit issues.
      start_index += len(response['items'])

      # Deduplicate issues in case crbug returns fewer issues than BATCH_SIZE
      # and then returns more issues than before. This can happen in rare cases
      # such as when a an issue is closed and then immediately reopened again
      # before we run the next query.
      new_issues = [issue for issue in response['items']
                    if issue['id'] not in seen_issue_ids]
      issues.extend(new_issues)
      seen_issue_ids.update(issue['id'] for issue in new_issues)

  # Retrieve description (first comment) for each issue.
  for issue in issues:
    request = service.issues.comments.list(
        projectId='chromium', issueId=issue['id'], body={'maxResults': 1})
    response = request.execute(num_retries=5)
    issue['description'] = response['items'][0]['content']

  return issues


def query(crbug_service_account):
  """Queries issue tracker for issues with Sheriff-* label.

  Returns:
    A dict mapping tree name to a list of issue dicts, each dict having the
    following properties:
      - key: 'crbug_issue_id:' + issue id.
      - title: summary of the issue.
      - body: description of the issue (first message).
      - links: list containing a single URL pair dict:
            [{'title': 'issue', 'href': 'https://crbug.com/issue_id'}]
      - start_time: time when issue was created.
      - type: 'crbug'
      - time: current time (updated each time builder_alerts is called).
      - severity: priority of the issue (or 4 for issues without priority).
      - tags: list containing second parts of all Sheriff-* labels in lower-case

    Example:
      {
        'chromium': [
          {
            'key': 'crbug_issue_id:536766',
            'title': 'Test/step "compile (with patch)" is flaky',
            'body': 'Test/step "compile (with patch)" is flaky.\n\nThis issue '
                    'was created automatically by the chromium-try-flakes...',
            'links': [{'title': 'issue', 'href: 'https://crbug.com/536766'}],
            'start_time': '2015-09-28T12:28:25Z',
            'time': '2015-10-02T09:07:55Z',
            'severity': 1,
            'tags': ['chromium', 'blink'],
            'type': 'crbug'
          },
          {
             ...
             'tags': ['chromium'],
             ...
          }
        ],
        'blink': [
          {
             ...
             'tags': ['chromium', 'blink'],
             ...
          },
          {
             ...
             'tags': ['blink'],
             ...
          },
        ],
        ...
      }
  """
  raw_issues = _list_issues(crbug_service_account)
  sheriff_issues = defaultdict(list)
  for raw_issue in raw_issues:
    sheriff_issue = {'key': 'crbug_issue_id:%d' % raw_issue['id'],
                     'title': 'crbug.com/%d' % raw_issue['id'],
                     'body': '',
                     'links': [{
                       'title': 'issue',
                       'href': 'https://crbug.com/%s' % raw_issue['id']
                     }],
                     'start_time': raw_issue['published'],
                     'time': datetime.datetime.utcnow().isoformat() + 'Z',
                     'type': 'crbug'}

    tags = set()
    severity = None
    for label in raw_issue['labels']:
      label = label.lower()
      if label.startswith('sheriff-'):
        tags.add(label[len('sheriff-'):])
      if label.startswith('pri-'):
        try:
          priority = int(label[len('pri-'):])
        except ValueError:  # invalid Pri-* label
          pass
        else:
          if not severity or priority < severity:  # return highest priority
            severity = priority

    sheriff_issue['tags'] = sorted(tags)  # converts back to list
    if severity is not None:
      sheriff_issue['severity'] = severity

    # We assume that a tags have 1:1 mapping to trees here.
    for tag in sheriff_issue['tags']:
      sheriff_issues[tag].append(sheriff_issue)

  return sheriff_issues
