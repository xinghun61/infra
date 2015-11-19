# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import datetime
import json

from apiclient import discovery
from apiclient.errors import HttpError
import httplib2
from oauth2client import client

from infra_libs import ts_mon


PROJECT_HOSTING_SCOPE = 'https://www.googleapis.com/auth/projecthosting'
DISCOVERY_URL = ('https://www.googleapis.com/discovery/v1/apis/{api}/'
                 '{apiVersion}/rest')

# Dictionary mapping whitelisted lower-case labels to corresponding tree names.
WHITELISTED_LABELS = {'sheriff-chromium': 'chromium',
                      'sheriff-blink': 'blink',
                      'infra-troopers': 'trooper'}
BATCH_SIZE = 10


issue_tracker_calls = (
    ts_mon.CounterMetric('flaky_issues_pipeline/issue_tracker_calls'))


def _build_crbug_service(crbug_service_account,
                         use_monorail):  # pragma: no cover
  with open(crbug_service_account) as crbug_sa_file:
    service_account = json.load(crbug_sa_file)

  creds = client.SignedJwtAssertionCredentials(
      service_account['client_email'], service_account['private_key'],
      PROJECT_HOSTING_SCOPE)
  http = creds.authorize(httplib2.Http())
  api_name = 'monorail' if use_monorail else 'projecthosting'
  api_version = 'v1' if use_monorail else 'v2'
  return discovery.build(
      api_name, api_version, discoveryServiceUrl=DISCOVERY_URL, http=http)


def _list_issues(crbug_service_account, use_monorail):
  service = _build_crbug_service(crbug_service_account, use_monorail)
  issues = []
  seen_issue_ids = set()
  for whitelisted_label in WHITELISTED_LABELS:
    start_index = 0
    while True:
      request = service.issues().list(
          projectId='chromium', label=whitelisted_label,
          startIndex=start_index, maxResults=BATCH_SIZE, can='open')
      issue_tracker_calls.increment({
        'project': 'chromium', 'label': whitelisted_label,
        'source': 'builder_alerts',
        'tracker': 'monorail' if use_monorail else 'codesite'})
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
      # such as when an issue is closed and then immediately reopened again
      # before we run the next query.
      new_issues = [issue for issue in response['items']
                    if issue['id'] not in seen_issue_ids]
      issues.extend(new_issues)
      seen_issue_ids.update(issue['id'] for issue in new_issues)

  return issues


def query(crbug_service_account, use_monorail):
  """Queries issue tracker for issues with whitelisted labels.

  Raises QuotaExceededError if requests result in quota errors. Callers should
  retry calling this function again later.

  Returns:
    A dict mapping tree name to a list of issue dicts, each dict having the
    following properties:
      - key: 'crbug_issue_id:' + issue id.
      - title: summary of the issue.
      - body: '' (empty).
      - links: list containing a single URL pair dict:
            [{'title': 'issue', 'href': 'https://crbug.com/issue_id'}]
      - start_time: time when issue was created.
      - type: 'crbug'
      - time: current time (updated each time builder_alerts is called).
      - severity: priority of the issue (or 4 for issues without priority).
      - tags: list containing tree names corresponding to labels.

    Example:
      {
        'chromium': [
          {
            'key': 'crbug_issue_id:536766',
            'title': 'Test/step "compile (with patch)" is flaky',
            'body': '',
            'links': [{'title': 'issue', 'href: 'https://crbug.com/536766'}],
            'start_time': '2015-09-28T12:28:25Z',
            'time': '2015-10-02T09:07:55Z',
            'severity': 1,
            'tags': ['chromium', 'trooper'],
            'type': 'crbug'
          },
          {
             ...
             'tags': ['chromium'],
             ...
          }
        ],
        'trooper': [
          {
             ...
             'tags': ['chromium', 'trooper'],
             ...
          },
          {
             ...
             'tags': ['trooper'],
             ...
          },
        ],
        'foobar': [],
        ...
      }
  """
  # Initialize each tree with an empty list to ensure that we POST updates into
  # each tree's endpoint even if there are no current issues.
  sheriff_issues = {}
  whitelisted_trees = WHITELISTED_LABELS.values()
  for tree_name in whitelisted_trees:
    sheriff_issues[tree_name] = []

  raw_issues = _list_issues(crbug_service_account, use_monorail)
  for raw_issue in raw_issues:
    sheriff_issue = {'key': 'crbug_issue_id:%d' % raw_issue['id'],
                     'title': raw_issue['title'],
                     'body': '',
                     'links': [{
                       'title': 'crbug.com/%d' % raw_issue['id'],
                       'href': 'https://crbug.com/%s' % raw_issue['id']
                     }],
                     'start_time': raw_issue['published'],
                     'time': datetime.datetime.utcnow().isoformat() + 'Z',
                     'type': 'crbug'}

    tags = set()
    severity = None
    for label in raw_issue['labels']:
      label = label.lower()
      if label in WHITELISTED_LABELS:
        tree_name = WHITELISTED_LABELS[label]
        tags.add(tree_name)
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
    for tree_name in sheriff_issue['tags']:
      sheriff_issues[tree_name].append(sheriff_issue)

  return sheriff_issues
