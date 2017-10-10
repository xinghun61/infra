# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the projectsearch module."""

import unittest

import mox

from framework import profiler
from proto import project_pb2
from services import service_manager
from sitewide import projectsearch
from testing import fake
from testing import testing_helpers


class ProjectSearchTest(unittest.TestCase):

  def setUp(self):
    self.services = service_manager.Services(
        project=fake.ProjectService())

    for idx, letter in enumerate('abcdefghijklmnopqrstuvwxyz'):
      self.services.project.TestAddProject(letter, project_id=idx + 1)
    for idx in range(27, 110):
      self.services.project.TestAddProject(str(idx), project_id=idx)

    self.mox = mox.Mox()
    self.mox.StubOutWithMock(self.services.project, 'GetVisibleLiveProjects')

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def TestPipeline(self, expected_last, expected_len):
    mr = testing_helpers.MakeMonorailRequest()

    mr.can = 1
    prof = profiler.Profiler()

    pipeline = projectsearch.ProjectSearchPipeline(mr, self.services, prof)
    pipeline.SearchForIDs()
    pipeline.GetProjectsAndPaginate('fake cnxn', '/hosting/search')
    self.assertEqual(1, pipeline.pagination.start)
    self.assertEqual(expected_last, pipeline.pagination.last)
    self.assertEqual(expected_len, len(pipeline.visible_results))

    return pipeline

  def SetUpZeroResults(self):
    self.services.project.GetVisibleLiveProjects(
        mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg(),
        use_cache=True).AndReturn([])

  def testZeroResults(self):
    self.SetUpZeroResults()
    self.mox.ReplayAll()
    pipeline = self.TestPipeline(0, 0)
    self.mox.VerifyAll()
    self.assertListEqual([], pipeline.visible_results)

  def SetUpNonzeroResults(self):
    self.services.project.GetVisibleLiveProjects(
        mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg(),
        use_cache=True).AndReturn([1, 2, 3])

  def testNonzeroResults(self):
    self.SetUpNonzeroResults()
    self.mox.ReplayAll()
    pipeline = self.TestPipeline(3, 3)
    self.mox.VerifyAll()
    self.assertListEqual(
        [1, 2, 3], [p.project_id for p in pipeline.visible_results])

  def SetUpTwoPageResults(self):
    self.services.project.GetVisibleLiveProjects(
        mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg(),
        use_cache=True).AndReturn(range(1, 106))

  def testTwoPageResults(self):
    """Test more than one pagination page of results."""
    self.SetUpTwoPageResults()
    self.mox.ReplayAll()
    pipeline = self.TestPipeline(100, 100)
    self.mox.VerifyAll()
    self.assertEqual(
        '/hosting/search?num=100&start=100', pipeline.pagination.next_url)
