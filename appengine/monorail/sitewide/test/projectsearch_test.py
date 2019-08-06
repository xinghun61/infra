# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Unittests for the projectsearch module."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import unittest

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
    self.services.project.GetVisibleLiveProjects = mock.MagicMock()

    for idx, letter in enumerate('abcdefghijklmnopqrstuvwxyz'):
      self.services.project.TestAddProject(letter, project_id=idx + 1)
    for idx in range(27, 110):
      self.services.project.TestAddProject(str(idx), project_id=idx)

    self.addCleanup(mock.patch.stopall())

  def TestPipeline(self, expected_last, expected_len):
    mr = testing_helpers.MakeMonorailRequest()
    mr.can = 1

    pipeline = projectsearch.ProjectSearchPipeline(mr, self.services)
    pipeline.SearchForIDs()
    pipeline.GetProjectsAndPaginate('fake cnxn', '/hosting/search')
    self.assertEqual(1, pipeline.pagination.start)
    self.assertEqual(expected_last, pipeline.pagination.last)
    self.assertEqual(expected_len, len(pipeline.visible_results))

    return pipeline

  def testZeroResults(self):
    self.services.project.GetVisibleLiveProjects.return_value = []

    pipeline = self.TestPipeline(0, 0)

    self.services.project.GetVisibleLiveProjects.assert_called_once()
    self.assertListEqual([], pipeline.visible_results)

  def testNonzeroResults(self):
    self.services.project.GetVisibleLiveProjects.return_value = [1, 2, 3]

    pipeline = self.TestPipeline(3, 3)

    self.services.project.GetVisibleLiveProjects.assert_called_once()
    self.assertListEqual(
        [1, 2, 3], [p.project_id for p in pipeline.visible_results])

  def testTwoPageResults(self):
    """Test more than one pagination page of results."""
    self.services.project.GetVisibleLiveProjects.return_value = list(
        range(1, 106))

    pipeline = self.TestPipeline(100, 100)

    self.services.project.GetVisibleLiveProjects.assert_called_once()
    self.assertEqual(
        '/hosting/search?num=100&start=100', pipeline.pagination.next_url)
