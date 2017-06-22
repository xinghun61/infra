# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock
import unittest

from infra.services.bugdroid import bugdroid
from infra.services.bugdroid import gob_helper
from infra.services.bugdroid import monorail_client
from infra.services.bugdroid.proto import repo_config_pb2
from infra_libs import ts_mon


class BugdroidGitPollerHandlerTest(unittest.TestCase):
  def setUp(self):
    self.monorail_client = mock.create_autospec(
        monorail_client.MonorailClient, spec_set=True, instance=True)
    self.logger = mock.create_autospec(
        logging.Logger, spec_set=True, instance=True)
    ts_mon.reset_for_unittest()

  def _make_handler(self, **kwargs):
    kwargs.setdefault('monorail', self.monorail_client)
    kwargs.setdefault('logger', self.logger)
    kwargs.setdefault('default_project', 'foo')
    kwargs.setdefault('no_merge', ['master'])
    kwargs.setdefault('public_bugs', True)
    kwargs.setdefault('test_mode', False)
    kwargs.setdefault('issues_labels', [])
    return bugdroid.BugdroidGitPollerHandler(**kwargs)

  def _make_commit(self, message):
    entry = gob_helper.GitLogEntry(
        'abcdef', ['123456'], 'Author', 'author@example.com', 'Committer',
        'committer@example.com', '2005-05-05 05:05:05.000000000',
        '2010-10-10 10:10:10.000000000', message,
        branch='refs/heads/branch',
        repo_url='https://example.googlesource.com/foo')
    entry.add_path('modify', 'modified/file', None)
    entry.add_path('add', 'added/file', None)
    entry.add_path('delete', 'gone', 'deleted/file')
    return entry

  def test_process_log_entry_no_bugs(self):
    handler = self._make_handler()
    handler.ProcessLogEntry(self._make_commit('Message with no bugs'))

    self.logger.info.assert_called_once_with(
        'Processing commit abcdef : bugs {}')
    self.assertFalse(self.monorail_client.get_issue.called)
    self.assertFalse(self.monorail_client.update_issue.called)

  def test_process_log_entry_default_project(self):
    handler = self._make_handler()

    issue = monorail_client.Issue(1234, [])
    self.monorail_client.get_issue.return_value = issue

    handler.ProcessLogEntry(self._make_commit('Message\nBug: 1234'))

    self.logger.info.assert_called_once_with(
        "Processing commit abcdef : bugs {'foo': [1234]}")
    self.monorail_client.get_issue.assert_called_once_with('foo', 1234)
    self.monorail_client.update_issue.assert_called_once_with(
        'foo', issue, True)
    self.assertEqual(
        'The following revision refers to this bug:\n'
        '  https://example.googlesource.com/foo/+/abcdef\n\n'
        'commit abcdef\n'
        'Author: Author <author@example.com>\n'
        'Date: Sun Oct 10 10:10:10 2010\n\n'
        'Message\n'
        'Bug: 1234\n'
        '[modify] https://crrev.com/abcdef/modified/file\n'
        '[add] https://crrev.com/abcdef/added/file\n'
        '[delete] https://crrev.com/123456/deleted/file\n', issue.comment)
    self.assertEqual(1,
        bugdroid.BugdroidGitPollerHandler.bug_comments_metric.get(
            {'project': 'foo', 'status': 'success'}))

  def test_process_log_entry_update_failure(self):
    handler = self._make_handler()

    class MyException(Exception):
      pass

    issue = monorail_client.Issue(1234, [])
    self.monorail_client.get_issue.return_value = issue
    self.monorail_client.update_issue.side_effect = MyException

    with self.assertRaises(MyException):
      handler.ProcessLogEntry(self._make_commit('Message\nBug: 1234'))

    self.assertEqual(1,
        bugdroid.BugdroidGitPollerHandler.bug_comments_metric.get(
            {'project': 'foo', 'status': 'failure'}))

  def test_process_log_entry_specified_project(self):
    handler = self._make_handler()

    issue = monorail_client.Issue(1234, [])
    self.monorail_client.get_issue.return_value = issue

    handler.ProcessLogEntry(self._make_commit('Message\nBug: bar:1234'))

    self.logger.info.assert_called_once_with(
        "Processing commit abcdef : bugs {'bar': [1234]}")
    self.monorail_client.get_issue.assert_called_once_with('bar', 1234)
    self.monorail_client.update_issue.assert_called_once_with(
        'bar', issue, True)
    self.assertEqual(
        'The following revision refers to this bug:\n'
        '  https://example.googlesource.com/foo/+/abcdef\n\n'
        'commit abcdef\n'
        'Author: Author <author@example.com>\n'
        'Date: Sun Oct 10 10:10:10 2010\n\n'
        'Message\n'
        'Bug: bar:1234\n'
        '[modify] https://crrev.com/abcdef/modified/file\n'
        '[add] https://crrev.com/abcdef/added/file\n'
        '[delete] https://crrev.com/123456/deleted/file\n', issue.comment)

  def test_process_log_entry_private_bugs(self):
    handler = self._make_handler(public_bugs=False)

    issue = monorail_client.Issue(1234, [])
    self.monorail_client.get_issue.return_value = issue

    handler.ProcessLogEntry(self._make_commit('Message\nBug: 1234'))

    self.logger.info.assert_called_once_with(
        "Processing commit abcdef : bugs {'foo': [1234]}")
    self.monorail_client.get_issue.assert_called_once_with('foo', 1234)
    self.monorail_client.update_issue.assert_called_once_with(
        'foo', issue, True)
    self.assertEqual(
        'The following revision refers to this bug:\n'
        '  https://example.googlesource.com/foo/+/abcdef\n\n'
        'commit abcdef\n'
        'Author: Author <author@example.com>\n'
        'Date: Sun Oct 10 10:10:10 2010\n', issue.comment)

  def test_process_log_entry_merge_label(self):
    handler = self._make_handler(issues_labels=[
        repo_config_pb2.Pair(key='merge', value='My-Label'),
    ])

    issue = monorail_client.Issue(1234, [])
    self.monorail_client.get_issue.return_value = issue

    handler.ProcessLogEntry(self._make_commit('Message\nBug: 1234'))
    self.assertTrue(issue.has_label('My-Label-branch'))

  def test_process_log_entry_approved_label(self):
    handler = self._make_handler(issues_labels=[
        repo_config_pb2.Pair(key='approved', value='My-Label'),
    ])

    issue = monorail_client.Issue(1234, ['My-Label'])
    self.monorail_client.get_issue.return_value = issue

    handler.ProcessLogEntry(self._make_commit('Message\nBug: 1234'))
    self.assertTrue(issue.has_label('-My-Label'))

  @mock.patch('infra.services.bugdroid.branch_utils.get_mstone')
  def test_process_log_entry_mstone_label(self, mock_get_mstone):
    handler = self._make_handler()

    mock_get_mstone.return_value = 'baz'

    issue = monorail_client.Issue(1234, ['merge-approved-baz'])
    self.monorail_client.get_issue.return_value = issue

    handler.ProcessLogEntry(self._make_commit('Message\nBug: 1234'))
    self.assertTrue(issue.has_label('-merge-approved-baz'))

  @mock.patch('infra.services.bugdroid.branch_utils.get_mstone')
  def test_process_log_entry_no_mstone(self, mock_get_mstone):
    handler = self._make_handler()

    mock_get_mstone.return_value = None

    issue = monorail_client.Issue(1234, ['merge-approved-baz'])
    self.monorail_client.get_issue.return_value = issue

    handler.ProcessLogEntry(self._make_commit('Message\nBug: 1234'))
    self.assertTrue(issue.has_label('merge-approved-baz'))
