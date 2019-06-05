# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for issuelist module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import time
import unittest

from framework import framework_constants
from framework import table_view_helpers
from proto import tracker_pb2
from testing import fake
from testing import testing_helpers
from tracker import tablecell


class DisplayNameMock(object):

  def __init__(self, name):
    self.display_name = name
    self.user = None


def MakeTestIssue(local_id, issue_id, summary):
  issue = tracker_pb2.Issue()
  issue.local_id = local_id
  issue.issue_id = issue_id
  issue.summary = summary
  return issue


class TableCellUnitTest(unittest.TestCase):

  USERS_BY_ID = {
      23456: DisplayNameMock('Jason'),
      34567: DisplayNameMock('Nathan'),
      }

  def setUp(self):
    self.issue1 = MakeTestIssue(
        local_id=1, issue_id=100001, summary='One')
    self.issue2 = MakeTestIssue(
        local_id=2, issue_id=100002, summary='Two')
    self.issue3 = MakeTestIssue(
        local_id=3, issue_id=100003, summary='Three')
    self.table_cell_kws = {
        'col': None,
        'users_by_id': self.USERS_BY_ID,
        'non_col_labels': [],
        'label_values': {},
        'related_issues': {},
        'config': 'fake config',
        }

  def testTableCellNote(self):
    table_cell_kws = self.table_cell_kws.copy()
    table_cell_kws.update({'note': ''})
    cell = tablecell.TableCellNote(
        self.issue1, **table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_NOTE)
    self.assertEqual(cell.values, [])

  def testTableCellNote_NoNote(self):
    table_cell_kws = self.table_cell_kws.copy()
    table_cell_kws.update({'note': 'some note'})
    cell = tablecell.TableCellNote(
        self.issue1, **table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_NOTE)
    self.assertEqual(cell.values[0].item, 'some note')

  def testTableCellDateAdded(self):
    table_cell_kws = self.table_cell_kws.copy()
    table_cell_kws.update({'date_added': 1234})
    cell = tablecell.TableCellDateAdded(
        self.issue1, **table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, 1234)

  def testTableCellAdderID(self):
    table_cell_kws = self.table_cell_kws.copy()
    table_cell_kws.update({'adder_id': 23456})
    cell = tablecell.TableCellAdderID(
        self.issue1, **table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, 'Jason')

  def testTableCellRank(self):
    table_cell_kws = self.table_cell_kws.copy()
    table_cell_kws.update({'issue_rank': 3})
    cell = tablecell.TableCellRank(
        self.issue1, **table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, 3)

  def testTableCellID(self):
    cell = tablecell.TableCellID(
        MakeTestIssue(4, 4, 'Four'), **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ID)
    # Note that the ID itself is accessed from the row, not the cell.

  def testTableCellOwner(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.owner_id=23456

    cell = tablecell.TableCellOwner(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, 'Jason')

  def testTableCellOwnerNoOwner(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.owner_id=framework_constants.NO_USER_SPECIFIED

    cell = tablecell.TableCellOwner(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values, [])

  def testTableCellReporter(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.reporter_id=34567

    cell = tablecell.TableCellReporter(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, 'Nathan')

  def testTableCellCc(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.cc_ids = [23456, 34567]

    cell = tablecell.TableCellCc(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, 'Jason')
    self.assertEqual(cell.values[1].item, 'Nathan')

  def testTableCellCcNoCcs(self):
    cell = tablecell.TableCellCc(
        MakeTestIssue(4, 4, 'Four'), **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values, [])

  def testTableCellAttachmentsNone(self):
    cell = tablecell.TableCellAttachments(
        MakeTestIssue(4, 4, 'Four'), **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, 0)

  def testTableCellAttachments(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.attachment_count = 2

    cell = tablecell.TableCellAttachments(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, 2)

  def testTableCellOpened(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.opened_timestamp = 1200000000

    cell = tablecell.TableCellOpened(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 'Jan 2008')

  def testTableCellClosed(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.closed_timestamp = None

    cell = tablecell.TableCellClosed(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values, [])

    test_issue.closed_timestamp = 1200000000
    cell = tablecell.TableCellClosed(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 'Jan 2008')

  def testTableCellModified(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.modified_timestamp = None

    cell = tablecell.TableCellModified(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values, [])

    test_issue.modified_timestamp = 1200000000
    cell = tablecell.TableCellModified(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 'Jan 2008')

  def testTableCellOwnerLastVisit(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.owner_id = None

    cell = tablecell.TableCellOwnerLastVisit(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values, [])

    test_issue.owner_id = 23456
    self.USERS_BY_ID[23456].user = testing_helpers.Blank(last_visit_timestamp=0)
    cell = tablecell.TableCellOwnerLastVisit(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values, [])

    self.USERS_BY_ID[23456].user.last_visit_timestamp = int(time.time())
    cell = tablecell.TableCellOwnerLastVisit(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 'Today')

    self.USERS_BY_ID[23456].user.last_visit_timestamp = (
        int(time.time()) - 25 * framework_constants.SECS_PER_HOUR)
    cell = tablecell.TableCellOwnerLastVisit(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 'Yesterday')

  def testTableCellBlockedOn(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.blocked_on_iids = [
        self.issue1.issue_id, self.issue2.issue_id, self.issue3.issue_id]
    table_cell_kws = self.table_cell_kws.copy()
    table_cell_kws['related_issues'] = {
        self.issue1.issue_id: self.issue1, self.issue2.issue_id: self.issue2,
        self.issue3.issue_id: self.issue3}

    cell = tablecell.TableCellBlockedOn(
        test_issue, **table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, '1')
    self.assertEqual(cell.values[1].item, '2')
    self.assertEqual(cell.values[2].item, '3')

  def testTableCellBlockedOnNone(self):
    cell = tablecell.TableCellBlockedOn(
        MakeTestIssue(4, 4, 'Four'), **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values, [])

  def testTableCellBlocking(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.blocking_iids = [
        self.issue1.issue_id, self.issue2.issue_id, self.issue3.issue_id]
    table_cell_kws = self.table_cell_kws.copy()
    table_cell_kws['related_issues'] = {
        self.issue1.issue_id: self.issue1, self.issue2.issue_id: self.issue2,
        self.issue3.issue_id: self.issue3}

    cell = tablecell.TableCellBlocking(
        test_issue, **table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, '1')
    self.assertEqual(cell.values[1].item, '2')
    self.assertEqual(cell.values[2].item, '3')

  def testTableCellBlockingNone(self):
    cell = tablecell.TableCellBlocking(
        MakeTestIssue(4, 4, 'Four'),
        **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values, [])

  def testTableCellBlocked(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.blocked_on_iids = [1, 2, 3]

    cell = tablecell.TableCellBlocked(
        test_issue, **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, 'Yes')

  def testTableCellBlockedNotBlocked(self):
    cell = tablecell.TableCellBlocked(
        MakeTestIssue(4, 4, 'Four'), **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, 'No')

  def testTableCellMergedInto(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.merged_into = self.issue3.issue_id
    table_cell_kws = self.table_cell_kws.copy()
    table_cell_kws['related_issues'] = {self.issue3.issue_id: self.issue3}

    cell = tablecell.TableCellMergedInto(
        test_issue, **table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values[0].item, '3')

  def testTableCellMergedIntoNotMerged(self):
    cell = tablecell.TableCellMergedInto(
        MakeTestIssue(4, 4, 'Four'), **self.table_cell_kws)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual(cell.values, [])

  def testTableCellAllLabels(self):
    labels = ['A', 'B', 'C', 'D-E', 'F-G']
    derived_labels = ['W', 'X', 'Y-Z']

    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.labels = labels
    test_issue.derived_labels = derived_labels

    cell = tablecell.TableCellAllLabels(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_ATTR)
    self.assertEqual([v.item for v in cell.values], labels + derived_labels)


class TableCellCSVTest(unittest.TestCase):

  USERS_BY_ID = {
      23456: DisplayNameMock('Jason'),
      }

  def testTableCellOpenedTimestamp(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.opened_timestamp = 1200000000

    cell = tablecell.TableCellOpenedTimestamp(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 1200000000)

  def testTableCellClosedTimestamp(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.closed_timestamp = None

    cell = tablecell.TableCellClosedTimestamp(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 0)

    test_issue.closed_timestamp = 1200000000
    cell = tablecell.TableCellClosedTimestamp(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 1200000000)

  def testTableCellModifiedTimestamp(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.modified_timestamp = 0

    cell = tablecell.TableCellModifiedTimestamp(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 0)

    test_issue.modified_timestamp = 1200000000
    cell = tablecell.TableCellModifiedTimestamp(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 1200000000)

  def testTableCellOwnerModifiedTimestamp(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.owner_modified_timestamp = 0

    cell = tablecell.TableCellOwnerModifiedTimestamp(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 0)

    test_issue.owner_modified_timestamp = 1200000000
    cell = tablecell.TableCellOwnerModifiedTimestamp(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 1200000000)

  def testTableCellStatusModifiedTimestamp(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.status_modified_timestamp = 0

    cell = tablecell.TableCellStatusModifiedTimestamp(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 0)

    test_issue.status_modified_timestamp = 1200000000
    cell = tablecell.TableCellStatusModifiedTimestamp(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 1200000000)

  def testTableCellComponentModifiedTimestamp(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.component_modified_timestamp = 0

    cell = tablecell.TableCellComponentModifiedTimestamp(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 0)

    test_issue.component_modified_timestamp = 1200000000
    cell = tablecell.TableCellComponentModifiedTimestamp(test_issue)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(cell.values[0].item, 1200000000)

  def testTableCellOwnerLastVisitDaysAgo(self):
    test_issue = MakeTestIssue(4, 4, 'Four')
    test_issue.owner_id = None

    cell = tablecell.TableCellOwnerLastVisitDaysAgo(
        test_issue, users_by_id=self.USERS_BY_ID)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(None, cell.values[0].item)

    test_issue.owner_id = 23456
    self.USERS_BY_ID[23456].user = testing_helpers.Blank(last_visit_timestamp=0)
    cell = tablecell.TableCellOwnerLastVisitDaysAgo(
        test_issue, users_by_id=self.USERS_BY_ID)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(None, cell.values[0].item)

    self.USERS_BY_ID[23456].user.last_visit_timestamp = (
        int(time.time()) - 25 * 60 * 60)
    cell = tablecell.TableCellOwnerLastVisitDaysAgo(
        test_issue, users_by_id=self.USERS_BY_ID)
    self.assertEqual(cell.type, table_view_helpers.CELL_TYPE_UNFILTERABLE)
    self.assertEqual(1, cell.values[0].item)
