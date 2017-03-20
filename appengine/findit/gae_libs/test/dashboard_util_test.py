# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from google.appengine.ext import ndb
from google.appengine.datastore.datastore_query import Cursor

from gae_libs import dashboard_util
from gae_libs import testcase
from libs import time_util


class Entity(ndb.Model):
  time = ndb.DateTimeProperty(indexed=True, auto_now_add=True)


class DashBoardUtilTest(testcase.TestCase):

  def setUp(self):
    super(DashBoardUtilTest, self).setUp()
    self.entities = [Entity(), Entity(), Entity()]
    for entity in self.entities:
      entity.put()

  @mock.patch.object(time_util, 'GetUTCNow')
  def testGetStartAndEndDates(self, mock_fn):
    """Tests getting start_date and end_date."""
    mock_now = datetime.datetime(2016, 10, 21, 1, 0, 0, 0)
    mock_midnight_yesterday = datetime.datetime(2016, 10, 20, 0, 0, 0, 0)
    mock_midnight_tomorrow = datetime.datetime(2016, 10, 22, 0, 0, 0, 0)
    mock_fn.return_value = mock_now
    start_date, end_date = dashboard_util.GetStartAndEndDates()
    self.assertEqual(start_date, mock_midnight_yesterday)
    self.assertEqual(end_date, mock_midnight_tomorrow)

  def testGetPagedResultsForDirectionNext(self):
    """Tests getting next page."""
    entities, _, _ = dashboard_util.GetPagedResults(
        Entity.query(), Entity.time, direction='next', page_size=1)
    self.assertEqual(len(entities), 1)
    self.assertEqual(entities, [self.entities[2]])

  def testGetPagedResultsForDirectionPrevious(self):
    """Tests getting previous page."""
    entities_on_page1, _, bottom_cursor1 = dashboard_util.GetPagedResults(
        Entity.query(), Entity.time, direction='next', page_size=1)
    _, top_cursor2, _ = dashboard_util.GetPagedResults(
        Entity.query(), Entity.time, cursor=bottom_cursor1, direction='next',
        page_size=1)
    back_to_page1_entities, _, _ = dashboard_util.GetPagedResults(
        Entity.query(), Entity.time, cursor=top_cursor2, direction='previous',
        page_size=1)
    self.assertListEqual(entities_on_page1, back_to_page1_entities)
