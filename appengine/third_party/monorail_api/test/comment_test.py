# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

import monorail_api


class IssueTestCase(unittest.TestCase):
  def test_creates_comment(self):
    comment = monorail_api.Comment({
      'author': {'name': 'test@example.com'},
      'content': 'TestComment',
      'published': '2016-01-10T21:33:44.123455Z',
      'id': '123',
      'updates': {
        'cc': ['-test@example.com', 'test2@example.com'],
        'labels': ['-LabelA', 'LabelB'],
        'components': ['-Test>Flaky', 'Test>Reliable'],
        'owner': 'test@example.com',
        'status': 'Assigned',
        'mergedInto': '456',
        'blockedOn': ['chromium:788'],
        'blocking': ['chromium:789'],
      }
    })

    self.assertEquals(comment.author, 'test@example.com')
    self.assertEquals(comment.comment, 'TestComment')
    self.assertEquals(
        comment.created, datetime.datetime(2016, 1, 10, 21, 33, 44, 123455))
    self.assertEquals(comment.id, '123')
    self.assertEquals(comment.cc, ['-test@example.com', 'test2@example.com'])
    self.assertEquals(comment.labels, ['-LabelA', 'LabelB'])
    self.assertEquals(comment.components, ['-Test>Flaky', 'Test>Reliable'])
    self.assertEquals(comment.owner, 'test@example.com')
    self.assertEquals(comment.status, 'Assigned')
    self.assertEquals(comment.merged_into, '456')
    self.assertEquals(comment.blocked_on, ['chromium:788'])
    self.assertEquals(comment.blocking, ['chromium:789'])

  def test_create_comment_without_updates(self):
    comment = monorail_api.Comment({
      'author': {'name': 'test@example.com'},
      'content': 'TestComment',
      'published': '2016-01-10T21:33:44.123455Z',
      'id': '123',
    })

    self.assertEquals(comment.cc, [])
    self.assertEquals(comment.labels, [])
    self.assertEquals(comment.components, [])
    self.assertIsNone(comment.owner)
    self.assertIsNone(comment.status)
    self.assertIsNone(comment.merged_into)
    self.assertEquals(comment.blocked_on, [])
    self.assertEquals(comment.blocking, [])
