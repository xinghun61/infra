# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from google.protobuf.field_mask_pb2 import FieldMask

from buildbucket_proto.build_pb2 import Build

from findit_v2.services import api
from findit_v2.services.context import Context

_MOCKED_LUCI_PROJECTS = {'project': {'ci': ['builder'],}}

_MOCKED_GERRIT_PROJECTS = {
    'project': {
        'name': 'project/name',
        'gitiles-host': 'gitiles.host.com',
    }
}


class APITest(unittest.TestCase):

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  def testNoSupportedProject(self, *_):
    self.assertFalse(
        api.OnBuildCompletion('unsupported-project', 'ci', 'builder', 123,
                              'FAILURE'))

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  def testNoSupportedci(self, *_):
    self.assertFalse(
        api.OnBuildCompletion('project', 'unsupported-ci', 'builder', 123,
                              'FAILURE'))

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  def testNoSupportedBuilder(self, *_):
    self.assertFalse(
        api.OnBuildCompletion('project', 'ci', 'unsupported-builder', 123,
                              'FAILURE'))

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  def testSkipNotFailedBuild(self, *_):
    self.assertFalse(
        api.OnBuildCompletion('project', 'ci', 'builder', 123, 'SUCCESS'))

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  @mock.patch('common.waterfall.buildbucket_client.GetV2Build')
  def testSkipFailedBuildNotMatchingGitilesProject(self, mocked_GetV2Build, *_):
    build = Build()
    build.input.gitiles_commit.host = 'wrong.host.com'
    build.input.gitiles_commit.project = 'wrong/project'
    mocked_GetV2Build.return_value = build
    self.assertFalse(
        api.OnBuildCompletion('project', 'ci', 'builder', 123, 'FAILURE'))
    mocked_GetV2Build.assert_called_once_with(
        123, fields=FieldMask(paths=['*']))

  @mock.patch('findit_v2.services.projects.LUCI_PROJECTS',
              _MOCKED_LUCI_PROJECTS)
  @mock.patch('findit_v2.services.projects.GERRIT_PROJECTS',
              _MOCKED_GERRIT_PROJECTS)
  @mock.patch('common.waterfall.buildbucket_client.GetV2Build')
  @mock.patch('findit_v2.services.detection.api.OnBuildFailure')
  def testValidFailedBuild(self, mocked_OnBuildFailure, mocked_GetV2Build, *_):
    build = Build()
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'
    mocked_GetV2Build.return_value = build
    self.assertTrue(
        api.OnBuildCompletion('project', 'ci', 'builder', 123, 'FAILURE'))
    mocked_GetV2Build.assert_called_once_with(
        123, fields=FieldMask(paths=['*']))
    mocked_OnBuildFailure.assert_called_once_with(
        Context(
            luci_project_name='project',
            gitiles_host='gitiles.host.com',
            gitiles_project='project/name',
            gitiles_ref='ref/heads/master',
            gitiles_id='git_sha'), build)
