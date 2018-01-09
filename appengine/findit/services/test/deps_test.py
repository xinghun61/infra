# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock
from testing_utils import testing

from common.findit_http_client import FinditHttpClient
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs.deps import chrome_dependency_fetcher
from libs.deps.dependency import Dependency
from libs.gitiles.diff import ChangeType
from services import deps
from services.parameters import BaseFailureInfo

_DEP_FETCHER = chrome_dependency_fetcher.ChromeDependencyFetcher(
    CachedGitilesRepository.Factory(FinditHttpClient()))


class DepsTest(testing.AppengineTestCase):

  def testGetOSPlatformName(self):
    master_name = 'chromium.linux'
    builder_name = 'android'
    self.assertEqual('android',
                     deps.GetOSPlatformName(master_name, builder_name))

  def testGetOSPlatformNameDefault(self):
    master_name = 'chromium.linux'
    builder_name = 'linux'
    self.assertEqual('unix', deps.GetOSPlatformName(master_name, builder_name))

  @mock.patch.object(logging, 'warning')
  def testGetOSPlatformNameNotFound(self, mock_logging):
    master_name = 'chromium'
    builder_name = 'other'
    self.assertEqual('all', deps.GetOSPlatformName(master_name, builder_name))
    mock_logging.assert_called_with(
        'Failed to detect the OS platform of builder "%s".', 'other')

  @mock.patch.object(_DEP_FETCHER, 'GetDependency')
  def testGetDependencies(self, mock_dep_fetcher):
    chromium_revision = 'rev2'
    os_platform = 'unix'
    mock_dep_fetcher.return_value = {
        'src': Dependency('src', 'https://url_src', 'rev2', 'DEPS'),
        'src/dep1': Dependency('src/dep1', 'https://url_dep1', '9', 'DEPS'),
    }

    expected_deps = {
        'src': {
            'repo_url': 'https://url_src',
            'revision': 'rev2',
        },
        'src/dep1': {
            'repo_url': 'https://url_dep1',
            'revision': '9',
        },
    }

    self.assertEqual(expected_deps,
                     deps.GetDependencies(chromium_revision, os_platform,
                                          _DEP_FETCHER))

  @mock.patch.object(_DEP_FETCHER, 'GetDependency')
  def testDetectDependencyRoll(self, mock_dep_fetcher):

    revision = 'rev2'
    change_log = {
        'touched_files': [
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'DEPS',
                'new_path': 'DEPS'
            },
        ]
    }
    os_platform = 'unix'

    mock_dep_fetcher.side_effect = [{
        'src': Dependency('src', 'https://url_src', 'rev2^', 'DEPS'),
        'src/dep1': Dependency('src/dep1', 'https://url_dep1', '7', 'DEPS'),
    }, {
        'src': Dependency('src', 'https://url_src', 'rev2', 'DEPS'),
        'src/dep1': Dependency('src/dep1', 'https://url_dep1', '9', 'DEPS'),
    }]

    expected_deps_roll = [
        {
            'path': 'src/dep1',
            'repo_url': 'https://url_dep1',
            'old_revision': '7',
            'new_revision': '9',
        },
    ]

    self.assertEqual(expected_deps_roll,
                     deps.DetectDependencyRoll(revision, change_log,
                                               os_platform, _DEP_FETCHER))

  def testDetectDependencyRollNotRoll(self):

    revision = 'rev2'
    change_log = {
        'touched_files': [
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'a.cc',
                'new_path': 'a.cc'
            },
        ]
    }
    os_platform = 'unix'

    self.assertEqual([],
                     deps.DetectDependencyRoll(revision, change_log,
                                               os_platform, _DEP_FETCHER))

  @mock.patch.object(deps, 'DetectDependencyRoll')
  def testDetectDependencyRolls(self, mock_roll):
    change_logs = {
        'rev1': {
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a.cc',
                    'new_path': 'a.cc'
                },
            ]
        },
        'rev2': {
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'DEPS',
                    'new_path': 'DEPS'
                },
            ]
        }
    }
    os_platform = 'unix'
    rev2_roll = [
        {
            'path': 'src/dep1',
            'repo_url': 'https://url_dep1',
            'old_revision': '7',
            'new_revision': '9',
        },
    ]

    mock_roll.side_effect = [[], rev2_roll]

    self.assertEqual({
        'rev2': rev2_roll
    }, deps.DetectDependencyRolls(change_logs, os_platform, _DEP_FETCHER))

  def testExtractDEPSInfo(self):

    def MockGetDependency(_, revision, os_platform):
      self.assertEqual('unix', os_platform)
      if revision == 'rev2':
        return {
            'src': Dependency('src', 'https://url_src', 'rev2', 'DEPS'),
            'src/dep1': Dependency('src/dep1', 'https://url_dep1', '9', 'DEPS'),
        }
      else:
        self.assertEqual('rev2^', revision)
        return {
            'src': Dependency('src', 'https://url_src', 'rev2^', 'DEPS'),
            'src/dep1': Dependency('src/dep1', 'https://url_dep1', '7', 'DEPS'),
        }

    failure_info = {
        'master_name': 'chromium.linux',
        'builder_name': 'Linux Tests',
        'build_number': 123,
        'chromium_revision': 'rev2',
        'failed': True,
    }
    change_logs = {
        'rev2': {
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'DEPS',
                    'new_path': 'DEPS'
                },
            ]
        },
        'rev1': {
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/file.cc',
                    'new_path': 'a/file.cc'
                },
            ]
        },
    }
    expected_deps_info = {
        'deps': {
            'src': {
                'repo_url': 'https://url_src',
                'revision': 'rev2',
            },
            'src/dep1': {
                'repo_url': 'https://url_dep1',
                'revision': '9',
            },
        },
        'deps_rolls': {
            'rev2': [
                {
                    'path': 'src/dep1',
                    'repo_url': 'https://url_dep1',
                    'old_revision': '7',
                    'new_revision': '9',
                },
            ]
        }
    }

    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
              'GetDependency', MockGetDependency)
    deps_info = deps.ExtractDepsInfo(
        BaseFailureInfo.FromSerializable(failure_info), change_logs)
    self.assertEqual(expected_deps_info, deps_info)
