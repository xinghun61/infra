# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

import monorail_api


class IssueTestCase(unittest.TestCase):
  def test_creates_issue(self):
    issue = monorail_api.Issue({
      'id': '123',
      'summary': 'TestSummary',
      'description': 'TestDescription',
      'status': 'Duplicate',
      'stars': '1',
      'state': 'closed',
      'author': {'name': 'test@example.com'},
      'owner': {'name': 'test2@example.com'},
      'labels': ['My-Label-1', 'My-Label-2'],
      'components': ['Component-1', 'Component-2'],
      'cc': [{'name': 'test2@example.com'}, {'name': 'test3@example.com'}],
      'published': '2016-01-10T21:33:44.123455Z',
      'closed': '2016-01-10T22:33:44.123455Z',
      'updated': '2016-01-10T23:33:44.123455Z',
      'mergedInto': {'issueId': '456'},
      'blockedOn': [{'issueId': '788'}],
      'blocking': [{'issueId': '789'}],
    })

    self.assertEquals(issue.id, '123')
    self.assertEquals(issue.blocked_on, ['788'])
    self.assertEquals(issue.blocking, ['789'])
    self.assertEquals(issue.merged_into, '456')
    self.assertEquals(
        issue.created, datetime.datetime(2016, 1, 10, 21, 33, 44, 123455))
    self.assertEquals(
        issue.updated, datetime.datetime(2016, 1, 10, 23, 33, 44, 123455))
    self.assertEquals(
        issue.closed, datetime.datetime(2016, 1, 10, 22, 33, 44, 123455))
    self.assertEquals(issue.summary, 'TestSummary')
    self.assertEquals(issue.description, 'TestDescription')
    self.assertEquals(issue.reporter, 'test@example.com')
    self.assertEquals(issue.owner, 'test2@example.com')
    self.assertEquals(issue.status, 'Duplicate')
    self.assertEquals(issue.stars, '1')
    self.assertFalse(issue.open)
    self.assertEquals(issue.labels, ['My-Label-1', 'My-Label-2'])
    self.assertEquals(issue.components, ['Component-1', 'Component-2'])
    self.assertEquals(issue.cc, ['test2@example.com', 'test3@example.com'])
    self.assertFalse(issue.dirty)

  def test_handles_dirty_status_and_list_of_changes_correctly(self):
    issue = monorail_api.Issue({})
    self.assertFalse(issue.dirty)
    self.assertEquals(issue.changed, set([]))

    issue.status = 'Available'
    self.assertTrue(issue.dirty)
    self.assertEquals(issue.changed, set(['status']))

    issue.setClean()
    self.assertFalse(issue.dirty)
    self.assertEquals(issue.changed, set([]))

    issue.cc.append('test@example.com')
    self.assertTrue(issue.dirty)
    self.assertEquals(issue.changed, set(['cc']))

    issue.setClean()
    self.assertFalse(issue.dirty)
    self.assertEquals(issue.changed, set([]))
