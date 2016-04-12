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

    self.mox = mox.Mox()
    self.mox.StubOutWithMock(self.services.project, 'GetVisibleLiveProjects')

  def tearDown(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()

  def TestPipeline(
      self, mr=None, expected_start=1, expected_last=None,
      expected_len=None):
    if not mr:
      mr = testing_helpers.MakeMonorailRequest()

    if expected_last is None and expected_len is not None:
      expected_last = expected_len

    mr.can = 1
    prof = profiler.Profiler()

    pipeline = projectsearch.ProjectSearchPipeline(mr, self.services, prof)
    pipeline.SearchForIDs()
    pipeline.GetProjectsAndPaginate('fake cnxn', '/hosting/search')
    self.assertEqual(expected_start, pipeline.pagination.start)
    if expected_last is not None:
      self.assertEqual(expected_last, pipeline.pagination.last)
    if expected_len is not None:
      self.assertEqual(expected_len, len(pipeline.visible_results))

    return pipeline

  def SetUpZeroResults(self):
    self.services.project.GetVisibleLiveProjects(
        mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()).AndReturn([])

  def testZeroResults(self):
    self.SetUpZeroResults()
    self.mox.ReplayAll()
    pipeline = self.TestPipeline(
        expected_last=0, expected_len=0)
    self.mox.VerifyAll()
    self.assertListEqual([], pipeline.visible_results)

  def SetUpNonzeroResults(self):
    self.services.project.GetVisibleLiveProjects(
        mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()).AndReturn([1, 2, 3])

  def testNonzeroResults(self):
    self.SetUpNonzeroResults()
    self.mox.ReplayAll()
    pipeline = self.TestPipeline(
        expected_last=3, expected_len=3)
    self.mox.VerifyAll()
    self.assertListEqual(
        [1, 2, 3], [p.project_id for p in pipeline.visible_results])

  def SetUpTwoPageResults(self):
    self.services.project.GetVisibleLiveProjects(
        mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(
            range(1, 16))

  def testTwoPageResults(self):
    """Test more than one pagination page of results."""
    self.SetUpTwoPageResults()
    self.mox.ReplayAll()
    pipeline = self.TestPipeline(
        expected_last=10, expected_len=10)
    self.mox.VerifyAll()
    self.assertEqual(
        '/hosting/search?num=10&start=10', pipeline.pagination.next_url)


if __name__ == '__main__':
  unittest.main()
