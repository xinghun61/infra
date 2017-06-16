# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import apiclient.discovery
import mock
import unittest

from infra.services.bugdroid import monorail_client


class MonorailClientTest(unittest.TestCase):

  def setUp(self):
    self.mock_api_client = mock.Mock()
    self.client = monorail_client.MonorailClient(
        '', client=self.mock_api_client)

    # Alias these to make shorter lines below.
    self.get = self.mock_api_client.issues.return_value.get
    self.insert = (
        self.mock_api_client.issues.return_value.comments.return_value.insert)

  def test_get_issue(self):
    self.get.return_value.execute.return_value = {
      'id': 123,
      'labels': ['one', 'two'],
    }

    ret = self.client.get_issue('foo', 123)
    self.assertIsInstance(ret, monorail_client.Issue)
    self.assertEquals(123, ret.id)
    self.assertEquals(['one', 'two'], ret.labels)

    self.get.assert_called_once_with(projectId='foo', issueId=123)

  def test_get_issue_missing_labels(self):
    self.get.return_value.execute.return_value = {'id': 123}

    ret = self.client.get_issue('foo', 123)
    self.assertEquals([], ret.labels)

  def test_update_not_dirty_issue(self):
    issue = monorail_client.Issue(123, [])
    self.client.update_issue('foo', issue)
    self.assertFalse(self.insert.called)

  def test_update_issue_comment(self):
    issue = monorail_client.Issue(123, [])
    issue.set_comment('hello')
    self.client.update_issue('foo', issue)

    self.insert.assert_called_once_with(
        projectId='foo',
        issueId=123,
        sendEmail=True,
        body={
            'id': 123,
            'updates': {},
            'content': 'hello',
        })

  def test_update_issue_add_label(self):
    issue = monorail_client.Issue(123, [])
    issue.add_label('one')
    self.client.update_issue('foo', issue)

    self.insert.assert_called_once_with(
        projectId='foo',
        issueId=123,
        sendEmail=True,
        body={
            'id': 123,
            'updates': {'labels': ['one']},
        })

  def test_update_issue_add_existing_label(self):
    issue = monorail_client.Issue(123, ['one'])
    issue.add_label('one')
    self.client.update_issue('foo', issue)

    self.assertFalse(self.insert.called)

  def test_update_issue_remove_label(self):
    issue = monorail_client.Issue(123, ['one', 'two'])
    issue.remove_label('two')
    self.assertFalse(issue.has_label('two'))
    self.client.update_issue('foo', issue)

    self.insert.assert_called_once_with(
        projectId='foo',
        issueId=123,
        sendEmail=True,
        body={
            'id': 123,
            'updates': {'labels': ['-two']},
        })

  def test_update_issue_remove_non_existing_label(self):
    issue = monorail_client.Issue(123, ['one', 'two'])
    issue.remove_label('three')
    self.client.update_issue('foo', issue)

    self.assertFalse(self.insert.called)
