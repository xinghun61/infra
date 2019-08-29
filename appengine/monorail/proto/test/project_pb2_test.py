# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for project_pb2 functions."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from proto import project_pb2


class ProjectPb2Test(unittest.TestCase):

  def testMakeProject_Defaults(self):
    project = project_pb2.MakeProject('proj')
    self.assertEqual('proj', project.project_name)
    self.assertEqual(project_pb2.ProjectState.LIVE, project.state)
    self.assertEqual(project_pb2.ProjectAccess.ANYONE, project.access)
    self.assertFalse(project.read_only_reason)

  def testMakeProject_Everything(self):
    project = project_pb2.MakeProject(
        'proj', project_id=789, state=project_pb2.ProjectState.ARCHIVED,
        access=project_pb2.ProjectAccess.MEMBERS_ONLY, summary='sum',
        description='desc', moved_to='example.com',
        cached_content_timestamp=1234567890, owner_ids=[111],
        committer_ids=[222], contributor_ids=[333],
        read_only_reason='being migrated',
        home_page='example.com', docs_url='example.com/docs',
        source_url='example.com/src', logo_gcs_id='logo_id',
        logo_file_name='logo.gif')
    self.assertEqual('proj', project.project_name)
    self.assertEqual(789, project.project_id)
    self.assertEqual(project_pb2.ProjectState.ARCHIVED, project.state)
    self.assertEqual(project_pb2.ProjectAccess.MEMBERS_ONLY, project.access)
    self.assertEqual('sum', project.summary)
    self.assertEqual('desc', project.description)
    self.assertEqual('example.com', project.moved_to)
    self.assertEqual(1234567890, project.cached_content_timestamp)
    self.assertEqual([111], project.owner_ids)
    self.assertEqual([222], project.committer_ids)
    self.assertEqual([333], project.contributor_ids)
    self.assertEqual('being migrated', project.read_only_reason)
    self.assertEqual('example.com', project.home_page)
    self.assertEqual('example.com/docs', project.docs_url)
    self.assertEqual('example.com/src', project.source_url)
    self.assertEqual('logo_id', project.logo_gcs_id)
    self.assertEqual('logo.gif', project.logo_file_name)
