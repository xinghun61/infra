# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import mock
import re
import webapp2
import webtest

from google.appengine.api import users

from backend.handlers.update_repo_to_dep_path import GetRepoToDepPath
from backend.handlers.update_repo_to_dep_path import UpdateRepoToDepPath
from common.model.crash_config import CrashConfig
from common.appengine_testcase import AppengineTestCase
from frontend.handlers import crash_config
from libs.deps.dependency import Dependency


class MockChromeDependencyFetcher(object):

  def __init__(self, none_deps=False):
    self.none_deps = none_deps

  def GetDependency(self, *_):
    if not self.none_deps:
      return {
          'src': Dependency('src', 'https://chromium.git', 'master'),
          'src/v8': Dependency('src/v8', 'https://chromium.v8.git', 'master'),
      }

    return None


class UpdateRepoToDepPathTest(AppengineTestCase):
  """Tests utility functions and ``UpdateRepoToDepPath`` handler."""
  app_module = webapp2.WSGIApplication([
      ('/process/update-repo-to-dep-path', UpdateRepoToDepPath),
  ], debug=True)

  def setUp(self):
    super(UpdateRepoToDepPathTest, self).setUp()
    self.http_client_for_git = self.GetMockHttpClient()

  def testGetRepoToDepPath(self):
    """Tests ``GetRepoToDepPath`` function."""
    repo_to_dep_path = GetRepoToDepPath(MockChromeDependencyFetcher())
    expected_repo_dep_path = {
        'https://chromium.git': 'src',
        'https://chromium.v8.git': 'src/v8',
    }
    self.assertEqual(repo_to_dep_path, expected_repo_dep_path)

  def testGetRepoToDepPathFailedToFetchDEPS(self):
    """Tests ``GetRepoToDepPath`` returns None if failed to fetch DEPS."""
    repo_to_dep_path = GetRepoToDepPath(
        MockChromeDependencyFetcher(none_deps=True))
    self.assertIsNone(repo_to_dep_path)

  @mock.patch(
      'backend.handlers.update_repo_to_dep_path.GetRepoToDepPath')
  def testHandleGet(self, mocked_get_repo_to_dep_path):
    """Tests ``UpdateRepoToDepPath`` handler."""
    mock_repo_to_dep_path = {
        'https://chromium.git': 'src',
        'https://chromium.v8.git': 'src/v8',
    }
    mocked_get_repo_to_dep_path.return_value = mock_repo_to_dep_path
    response = self.test_app.get('/process/update-repo-to-dep-path',
                                 headers={'X-AppEngine-Cron': 'true'})
    self.assertEqual(response.status_int, 200)
    self.assertDictEqual(mock_repo_to_dep_path,
                         CrashConfig.Get().repo_to_dep_path)
