# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for monorail.search.backendsearch."""

import unittest
import mox

import settings
from search import backendsearch
from search import backendsearchpipeline
from services import service_manager
from testing import fake
from testing import testing_helpers


class BackendSearchTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        issue=fake.IssueService(),
        )
    self.mr = testing_helpers.MakeMonorailRequest(
        path='/_backend/besearch?q=Priority:High&shard=2')
    self.mr.query_project_names = ['proj']
    self.mr.specified_logged_in_user_id = 111L
    self.mr.specified_me_user_id = 222L
    self.mr.shard_id = 2
    self.servlet = backendsearch.BackendSearch(
        'req', 'res', services=self.services)
    self.mox = mox.Mox()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def testHandleRequest_NoResults(self):
    """Handle the case where the search has no results."""
    pipeline = testing_helpers.Blank(
        SearchForIIDs=lambda: None,
        result_iids=[],
        search_limit_reached=False,
        error=None)
    self.mox.StubOutWithMock(backendsearchpipeline, 'BackendSearchPipeline')
    backendsearchpipeline.BackendSearchPipeline(
      self.mr, self.services, 100, ['proj'], 111L, 222L
      ).AndReturn(pipeline)
    self.mox.ReplayAll()

    json_data = self.servlet.HandleRequest(self.mr)
    self.mox.VerifyAll()
    self.assertEqual([], json_data['unfiltered_iids'])
    self.assertFalse(json_data['search_limit_reached'])
    self.assertEqual(None, json_data['error'])

  def testHandleRequest_ResultsInOnePagainationPage(self):
    """Prefetch all result issues and return them."""
    allowed_iids = [1, 2, 3, 4, 5, 6, 7, 8]
    pipeline = testing_helpers.Blank(
        SearchForIIDs=lambda: None,
        result_iids=allowed_iids,
        search_limit_reached=False,
        error=None)
    self.mox.StubOutWithMock(backendsearchpipeline, 'BackendSearchPipeline')
    backendsearchpipeline.BackendSearchPipeline(
      self.mr, self.services, 100, ['proj'], 111L, 222L
      ).AndReturn(pipeline)
    self.mox.StubOutWithMock(self.services.issue, 'GetIssues')
    # All issues are prefetched because they fit  on the first pagination page.
    self.services.issue.GetIssues(self.mr.cnxn, allowed_iids, shard_id=2)
    self.mox.ReplayAll()

    json_data = self.servlet.HandleRequest(self.mr)
    self.mox.VerifyAll()
    self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8], json_data['unfiltered_iids'])
    self.assertFalse(json_data['search_limit_reached'])
    self.assertEqual(None, json_data['error'])

  def testHandleRequest_ResultsExceedPagainationPage(self):
    """Return all result issue IDs, but only prefetch the first page."""
    self.mr.num = 5
    pipeline = testing_helpers.Blank(
        SearchForIIDs=lambda: None,
        result_iids=[1, 2, 3, 4, 5, 6, 7, 8],
        search_limit_reached=False,
        error=None)
    self.mox.StubOutWithMock(backendsearchpipeline, 'BackendSearchPipeline')
    backendsearchpipeline.BackendSearchPipeline(
      self.mr, self.services, 100, ['proj'], 111L, 222L
      ).AndReturn(pipeline)
    self.mox.StubOutWithMock(self.services.issue, 'GetIssues')
    # First 5 issues are prefetched because num=5
    self.services.issue.GetIssues(self.mr.cnxn, [1, 2, 3, 4, 5], shard_id=2)
    self.mox.ReplayAll()

    json_data = self.servlet.HandleRequest(self.mr)
    self.mox.VerifyAll()
    # All are IDs are returned to the frontend.
    self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8], json_data['unfiltered_iids'])
    self.assertFalse(json_data['search_limit_reached'])
    self.assertEqual(None, json_data['error'])

  def testHandleRequest_QueryError(self):
    """Handle the case where the search has no results."""
    error = ValueError('Malformed query')
    pipeline = testing_helpers.Blank(
        SearchForIIDs=lambda: None,
        result_iids=[],
        search_limit_reached=False,
        error=error)
    self.mox.StubOutWithMock(backendsearchpipeline, 'BackendSearchPipeline')
    backendsearchpipeline.BackendSearchPipeline(
      self.mr, self.services, 100, ['proj'], 111L, 222L
      ).AndReturn(pipeline)
    self.mox.ReplayAll()

    json_data = self.servlet.HandleRequest(self.mr)
    self.mox.VerifyAll()
    self.assertEqual([], json_data['unfiltered_iids'])
    self.assertFalse(json_data['search_limit_reached'])
    self.assertEqual(error.message, json_data['error'])
