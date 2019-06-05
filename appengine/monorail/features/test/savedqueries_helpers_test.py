# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unit tests for savedqueries_helpers feature."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

import mox

from features import savedqueries_helpers
from testing import fake
from tracker import tracker_bizobj


class SavedQueriesHelperTest(unittest.TestCase):

  def setUp(self):
    self.features = fake.FeaturesService()
    self.project = fake.ProjectService()
    self.cnxn = 'fake cnxn'
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testParseSavedQueries(self):
    post_data = {
        'xyz_savedquery_name_1': '',
        'xyz_savedquery_name_2': 'name2',
        'xyz_savedquery_name_3': 'name3',
        'xyz_savedquery_id_1': 1,
        'xyz_savedquery_id_2': 2,
        'xyz_savedquery_id_3': 3,
        'xyz_savedquery_projects_1': '123',
        'xyz_savedquery_projects_2': 'abc',
        'xyz_savedquery_projects_3': 'def',
        'xyz_savedquery_base_1': 4,
        'xyz_savedquery_base_2': 5,
        'xyz_savedquery_base_3': 6,
        'xyz_savedquery_query_1': 'query1',
        'xyz_savedquery_query_2': 'query2',
        'xyz_savedquery_query_3': 'query3',
        'xyz_savedquery_sub_mode_1': 'sub_mode1',
        'xyz_savedquery_sub_mode_2': 'sub_mode2',
        'xyz_savedquery_sub_mode_3': 'sub_mode3',
    }
    self.project.TestAddProject(name='abc', project_id=1001)
    self.project.TestAddProject(name='def', project_id=1002)

    saved_queries = savedqueries_helpers.ParseSavedQueries(
        self.cnxn, post_data, self.project, prefix='xyz_')
    self.assertEqual(2, len(saved_queries))

    # pylint: disable=unbalanced-tuple-unpacking
    saved_query1, saved_query2 = saved_queries
    # Assert contents of saved_query1.
    self.assertEqual(2, saved_query1.query_id)
    self.assertEqual('name2', saved_query1.name)
    self.assertEqual(5, saved_query1.base_query_id)
    self.assertEqual('query2', saved_query1.query)
    self.assertEqual([1001], saved_query1.executes_in_project_ids)
    self.assertEqual('sub_mode2', saved_query1.subscription_mode)
    # Assert contents of saved_query2.
    self.assertEqual(3, saved_query2.query_id)
    self.assertEqual('name3', saved_query2.name)
    self.assertEqual(6, saved_query2.base_query_id)
    self.assertEqual('query3', saved_query2.query)
    self.assertEqual([1002], saved_query2.executes_in_project_ids)
    self.assertEqual('sub_mode3', saved_query2.subscription_mode)

  def testSavedQueryToCond(self):
    class MockSavedQuery:
      def __init__(self):
        self.base_query_id = 1
        self.query = 'query'
    saved_query = MockSavedQuery()

    cond_for_missing_query = savedqueries_helpers.SavedQueryToCond(None)
    self.assertEquals('', cond_for_missing_query)

    cond_with_no_base = savedqueries_helpers.SavedQueryToCond(saved_query)
    self.assertEquals('query', cond_with_no_base)

    self.mox.StubOutWithMock(tracker_bizobj, 'GetBuiltInQuery')
    tracker_bizobj.GetBuiltInQuery(1).AndReturn('base')
    self.mox.ReplayAll()
    cond_with_base = savedqueries_helpers.SavedQueryToCond(saved_query)
    self.assertEquals('base query', cond_with_base)
    self.mox.VerifyAll()

  def testSavedQueryIDToCond(self):
    self.mox.StubOutWithMock(savedqueries_helpers, 'SavedQueryToCond')
    savedqueries_helpers.SavedQueryToCond(mox.IgnoreArg()).AndReturn('ret')
    self.mox.ReplayAll()
    query_cond = savedqueries_helpers.SavedQueryIDToCond(
        self.cnxn, self.features, 1)
    self.assertEquals('ret', query_cond)
    self.mox.VerifyAll()

    self.mox.StubOutWithMock(tracker_bizobj, 'GetBuiltInQuery')
    tracker_bizobj.GetBuiltInQuery(1).AndReturn('built_in_query')
    self.mox.ReplayAll()
    query_cond = savedqueries_helpers.SavedQueryIDToCond(
        self.cnxn, self.features, 1)
    self.assertEquals('built_in_query', query_cond)
    self.mox.VerifyAll()
