# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock
import logging
import tempfile
import unittest

from infra.services.bugdroid import gerrit_poller
from infra.services.bugdroid import gob_helper
from infra.services.bugdroid import poller_handlers

from infra_libs import ts_mon
import infra_libs


LOG_ENTRY_1 = gob_helper.GitLogEntry(
    'abcdef', [], 'Author 1', 'author1@example.com', 'Committer 1',
    'committer1@example.com', '2005-05-05 05:05:05.000000000',
    '2010-10-10 10:10:10.000000000', 'Message 1',
    branch='refs/heads/branch',
    repo_url='https://example.googlesource.com/foo')
LOG_ENTRY_1.update_date = '2005-05-05 05:05:05.000000000'
LOG_ENTRY_1.number = 42


LOG_ENTRY_2 = gob_helper.GitLogEntry(
    '123456', ['abcdef'], 'Author 2', 'author2@example.com', 'Committer 2',
    'committer2@example.com', '2006-06-06 06:06:06.000000000',
    '2011-11-11 11:11:11.000000000', 'Message 2',
    branch='refs/heads/branch',
    repo_url='https://example.googlesource.com/foo')
LOG_ENTRY_2.update_date = '2006-06-06 06:06:06.000000000'
LOG_ENTRY_2.number = 43


class GerritPollerTest(unittest.TestCase):
  def setUp(self):
    self.temp_dir = tempfile.mkdtemp()

    self.gerrit_helper_ctor = (
        mock.patch('infra.services.bugdroid.gob_helper.GerritHelper',
                   autospec=True).start())
    self.gerrit = self.gerrit_helper_ctor.return_value
    self.since_date = datetime.datetime(2000, 1, 1, 16, 20, 9, 171530)
    self.gerrit.GenerateTimeStamp.return_value = 'Wed Jan 1 16:20:14 2000'
    self.gerrit.ParseTimeStamp.return_value = self.since_date
    self.handler = mock.create_autospec(
        poller_handlers.BasePollerHandler, instance=True)
    self.handler.must_succeed = False

    self.poller = gerrit_poller.GerritPoller(
        'http://example.com', 'foo', datadir=self.temp_dir)
    self.poller.add_handler(self.handler)

    ts_mon.reset_for_unittest()

  def tearDown(self):
    mock.patch.stopall()

    infra_libs.rmtree(self.temp_dir)

  def test_success(self):
    self.gerrit.GetLogEntries.return_value = ([LOG_ENTRY_1, LOG_ENTRY_2], None)

    self.poller.execute()

    self.gerrit.GetLogEntries.assert_called_once_with(
        since=self.since_date, limit=1000, fields=[
            'CURRENT_COMMIT', 'CURRENT_REVISION', 'CURRENT_FILES'])
    self.handler.ProcessLogEntry.assert_has_calls([
        mock.call(LOG_ENTRY_2),
        mock.call(LOG_ENTRY_1)])
    self.assertEquals(2, self.poller.commits_metric.get(
        {'poller': 'gerrit', 'project': 'foo', 'status': 'success'}))

  def test_already_seen(self):
    self.gerrit.GetLogEntries.return_value = ([LOG_ENTRY_1], None)

    self.poller.seen_bitmap.SetBit(LOG_ENTRY_1.number)
    self.poller.execute()

    self.assertFalse(self.handler.ProcessLogEntry.called)
    self.assertEquals(1, self.poller.commits_metric.get(
        {'poller': 'gerrit', 'project': 'foo', 'status': 'seen'}))

  def test_handler_raises_exception(self):
    self.gerrit.GetLogEntries.return_value = ([LOG_ENTRY_1, LOG_ENTRY_2], None)
    self.handler.ProcessLogEntry.side_effect = (Exception, None)

    self.poller.execute()

    self.handler.ProcessLogEntry.assert_has_calls([
        mock.call(LOG_ENTRY_2),
        mock.call(LOG_ENTRY_1)])
    self.assertEquals(1, self.poller.commits_metric.get(
        {'poller': 'gerrit', 'project': 'foo', 'status': 'error'}))
    self.assertEquals(1, self.poller.commits_metric.get(
        {'poller': 'gerrit', 'project': 'foo', 'status': 'success'}))

  def test_must_succeed_handler_raises_exception(self):
    self.gerrit.GetLogEntries.return_value = ([LOG_ENTRY_1, LOG_ENTRY_2], None)
    self.handler.ProcessLogEntry.side_effect = Exception
    self.handler.must_succeed = True

    self.poller.execute()

    self.handler.ProcessLogEntry.assert_called_once_with(LOG_ENTRY_2)
    self.assertEquals(1, self.poller.commits_metric.get(
        {'poller': 'gerrit', 'project': 'foo', 'status': 'error'}))
    self.assertIsNone(self.poller.commits_metric.get(
        {'poller': 'gerrit', 'project': 'foo', 'status': 'success'}))

