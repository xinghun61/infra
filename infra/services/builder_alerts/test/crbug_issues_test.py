# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import unittest

from infra.services.builder_alerts import crbug_issues

from apiclient.errors import HttpError


CRBUG_ISSUES_LIST_TEST_REPLY = [
  {
    'kind': 'projecthosting#issue',
    'id': 123456,
    'title': 'TestTitle',
    'summary': 'TestTitle',
    'stars': 0,
    'starred': False,
    'status': 'Assigned',
    'state': 'open',
    'labels': [
      'Sheriff-Chromium',
      'Pri-2',
      'Via-TryFlakes',
      'Pri-1',
      'M-47',
      'Pri-2',
    ],
    'author': {
      'kind': 'projecthosting#issuePerson',
      'name': 'someone@chromium.org',
      'htmlLink': 'https://code.google.com/u/someone@chromium.org/'
    },
    'owner': {
      'kind': 'projecthosting#issuePerson',
      'name': 'anyone@chromium.org',
      'htmlLink': 'https://code.google.com/u/anyone@chromium.org/'
    },
    'updated': '2015-10-01T22:59:57.000Z',
    'published': '2015-10-01T22:59:56.000Z',
    'projectId': 'chromium',
    'canComment': True,
    'canEdit': True,
  },
  {
    'kind': 'projecthosting#issue',
    'id': 654321,
    'title': 'TestTitle',
    'summary': 'TestTitle',
    'stars': 1,
    'starred': False,
    'status': 'Available',
    'state': 'open',
    'labels': [
      'Pri-abc',
      'Sheriff-Blink',
      'Infra-Troopers',
      'Infra-TrOopErS',
      'Type-Bug',
      'Cr-Blink-PerformanceAPIs',
      'OS-All'
    ],
    'author': {
      'kind': 'projecthosting#issuePerson',
      'name': 'someone@chromium.org',
      'htmlLink': 'https://code.google.com/u/someone@chromium.org/'
    },
    'updated': '2015-10-02T09:55:32.000Z',
    'published': '2015-10-02T09:55:32.000Z',
    'projectId': 'chromium',
    'canComment': True,
    'canEdit': True,
  }
]



class CrbugIssuesQueryTest(unittest.TestCase):
  def setUp(self):
    list_issues_mock = mock.Mock()
    list_issues_mock.return_value = CRBUG_ISSUES_LIST_TEST_REPLY

    self._patchers = [
        mock.patch.object(crbug_issues, '_list_issues', list_issues_mock),
        mock.patch.object(crbug_issues, 'WHITELISTED_LABELS',
                          {'sheriff-chromium': 'chromium',
                           'infra-troopers': 'trooper',
                           'sheriff-foobar': 'foobar'}),
    ]
    for patcher in self._patchers:
      patcher.start()

  def tearDown(self):
    for patcher in self._patchers:
      patcher.stop()

  def test_correctly_sorts_issues_by_tree(self):
    issues_by_tree = crbug_issues.query('test-account.json')
    self.assertEqual(sorted(issues_by_tree.keys()),
                     ['chromium', 'foobar', 'trooper'])
    self.assertEqual(len(issues_by_tree['chromium']), 1)
    self.assertEqual(len(issues_by_tree['trooper']), 1)
    self.assertEqual(len(issues_by_tree['foobar']), 0)

  def test_retrieves_basic_issue_basic_properties(self):
    issues_by_tree = crbug_issues.query('test-account.json')
    issue = issues_by_tree['chromium'][0]
    self.assertEqual(issue.get('key'), 'crbug_issue_id:123456')
    self.assertEqual(issue.get('title'), 'TestTitle')
    self.assertEqual(issue.get('body'), '')
    self.assertEqual(
        issue.get('links'),
        [{'title': 'crbug.com/123456', 'href': 'https://crbug.com/123456'}])
    self.assertEqual(issue.get('start_time'), '2015-10-01T22:59:56.000Z')
    self.assertEqual(issue.get('type'), 'crbug')
    self.assertEqual(issue.get('severity'), 1)  # highest of two priority labels
    self.assertEqual(issue.get('tags'), ['chromium'])

  def test_reports_utctime_on_returned_issues(self):
    # Mock built-in datetime.datetime.utcnow manually. See
    # http://stackoverflow.com/q/4481954 for more details why.
    class MockDateTime(datetime.datetime):
      @classmethod
      def utcnow(cls):
        return datetime.datetime(2015, 10, 2, 22, 0, 0)
    old_datetime = datetime.datetime
    datetime.datetime = MockDateTime

    issues_by_tree = crbug_issues.query('test-account.json')
    issue = issues_by_tree['chromium'][0]
    self.assertEqual(issue.get('time'), '2015-10-02T22:00:00Z')

    datetime.datetime = old_datetime

  def test_parses_tags_correctly(self):
    issues_by_tree = crbug_issues.query('test-account.json')
    issue = issues_by_tree['trooper'][0]
    self.assertEqual(issue.get('tags'), ['trooper'])

  def test_correct_severity_for_issues_with_no_priority(self):
    issues_by_tree = crbug_issues.query('test-account.json')
    issue = issues_by_tree['trooper'][0]
    self.assertIsNone(issue.get('severity'))


class CrbugIssuesListTest(unittest.TestCase):
  def setUp(self):
    crbug_service_mock = mock.Mock()
    issues_mock = crbug_service_mock.issues.return_value
    self.list_mock = issues_mock.list.return_value

    self._patchers = [
        mock.patch.object(crbug_issues, '_build_crbug_service',
                          lambda _: crbug_service_mock),
        # Tests below expect only a single sequence of calls to issue tracker
        # API iterating over all issues, so we mock whitelisted labels to only
        # contain a single entry.
        mock.patch.object(crbug_issues, 'WHITELISTED_LABELS',
                          {'sheriff-chromium': 'chromium'}),
    ]
    for patcher in self._patchers:
      patcher.start()

  def tearDown(self):
    for patcher in self._patchers:
      patcher.stop()

  def test_correctly_stops_on_no_results(self):
    self.list_mock.execute.side_effect = [
        {'items': [{'id': 1}, {'id': 2}, {'id': 3}]},
        {},
        {'items': [{'id': 4}]},
    ]

    issues = crbug_issues._list_issues('test-account.json')
    self.assertEqual(len(issues), 3)

  def test_correctly_stops_on_empty_results(self):
    self.list_mock.execute.side_effect = [
        {'items': [{'id': 1}, {'id': 2}, {'id': 3}]},
        {'items': []},
        {'items': [{'id': 4}]},
    ]

    issues = crbug_issues._list_issues('test-account.json')
    self.assertEqual(len(issues), 3)

  def test_correctly_deduplicates_results(self):
    self.list_mock.execute.side_effect = [
        {'items': [{'id': 1}, {'id': 2}, {'id': 3}]},
        {'items': [{'id': 2}, {'id': 3}, {'id': 4}]},
        {},
    ]

    issues = crbug_issues._list_issues('test-account.json')
    self.assertEqual(len(issues), 4)
    self.assertEqual([1, 2, 3, 4], [issue['id'] for issue in issues])
