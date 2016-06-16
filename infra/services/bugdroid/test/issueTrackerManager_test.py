# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

import infra.services.bugdroid.IssueTrackerManager as IssueTrackerManager


class IssueTrackerManagerTest(unittest.TestCase):

  def test_convertEntryToComment(self):
    entry = {
      'author': {'name': 'author@example.com'},
      'content': 'test comment',
      'published': '2016-12-25T13:23:34',
      'id': '10001',
      'updates': {
        'cc': ['user@example.com'],
        'labels': ['pri-1'],
        'owner': 'owner@example.com',
        'status': 'New',
        'summary': 'Test summary',
        'mergedInto': ['10002']
      },
    }

    cmnt = IssueTrackerManager.convertEntryToComment(entry)
    self.assertEqual('author@example.com', cmnt.author)
    self.assertEqual('test comment', cmnt.comment)
    self.assertEqual(datetime.datetime(2016, 12, 25, 13, 23, 34), cmnt.created)
    self.assertEqual('10001', cmnt.id)
    self.assertEqual(['user@example.com'], cmnt.cc)
    self.assertEqual(['pri-1'], cmnt.labels)
    self.assertEqual('owner@example.com', cmnt.owner)
    self.assertEqual('New', cmnt.status)
    self.assertEqual('Test summary', cmnt.summary)
    self.assertEqual(['10002'], cmnt.merged_into)

  def test_parseDateTime(self):
    dt1 = '2016-12-25T13:23:34'
    dt2 = '2016-12-25T13:23:34.432Z'
    self.assertEqual(datetime.datetime(2016, 12, 25, 13, 23, 34),
                     IssueTrackerManager.parseDateTime(dt1))
    self.assertEqual(datetime.datetime(2016, 12, 25, 13, 23, 34, 432),
                     IssueTrackerManager.parseDateTime(dt2))

  def test_convertEntryToIssue(self):
    entry = {
      'author': {'name': 'author@example.com'},
      'owner': {'name': 'owner@example.com'},
      'published': '2016-12-25T13:23:34',
      'updated': '2016-12-26T13:23:34',
      'id': '10001',
      'blockedOn': [{'issueId': '10002'}],
      'mergedInto': {'issueId': '10003'},
      'summary': 'Test issue summary',
      'stars': 1,
      'state': 'open',
      'status': 'New',
      'labels': ['pri-1'],
    }
    issue = IssueTrackerManager.convertEntryToIssue(entry, None)
    self.assertEqual('10001', issue.id)
    self.assertEqual(['10002'], issue.blocked_on)
    self.assertEqual(datetime.datetime(2016, 12, 25, 13, 23, 34),
                     issue.created)
    self.assertEqual('Test issue summary', issue.summary)
    self.assertEqual('author@example.com', issue.reporter)
    self.assertEqual('owner@example.com', issue.owner)
    self.assertEqual('New', issue.status)
    self.assertEqual(1, issue.stars)
    self.assertTrue(issue.open)
    self.assertEqual(['pri-1'], issue.labels)
