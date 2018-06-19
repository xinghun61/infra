# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import mock

from testing_utils import testing

from gae_libs.http.http_client_appengine import HttpClientAppengine
from libs.deps import deps_parser
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll
from libs.deps import chrome_dependency_fetcher
from libs.gitiles import gitiles_repository
from libs.gitiles.gitiles_repository import GitilesRepository

DEPS_GIT = '.DEPS.git'
DEPS = 'DEPS'
DEPS_GIT_CONTENT = '.DEPS.git content'
DEPS_CONTENT = 'DEPS test'


class ChromiumDEPSTest(testing.AppengineTestCase):
  deps_downloader = chrome_dependency_fetcher.DEPSDownloader(
      gitiles_repository.GitilesRepository.Factory(HttpClientAppengine()))
  chrome_dep_fetcher = chrome_dependency_fetcher.ChromeDependencyFetcher(
      gitiles_repository.GitilesRepository.Factory(HttpClientAppengine()))

  @mock.patch.object(GitilesRepository, 'GetSource', side_effect=[DEPS_CONTENT])
  def testUseDEPS(self, mock_source):
    revision = 'abc'

    content = self.deps_downloader.Load(
        chrome_dependency_fetcher._CHROMIUM_REPO_MASTER, revision, 'DEPS')
    self.assertEqual(DEPS_CONTENT, content)
    mock_source.assert_called_once_with(DEPS, revision)

  @mock.patch.object(
      GitilesRepository, 'GetSource', side_effect=[None, DEPS_GIT_CONTENT])
  def testUseDEPS_GIT(self, mock_source):
    revision = 'abc'

    content = self.deps_downloader.Load(
        chrome_dependency_fetcher._CHROMIUM_REPO_MASTER, revision, 'DEPS')
    self.assertEqual(DEPS_GIT_CONTENT, content)
    mock_source.assert_has_calls(
        [mock.call(DEPS, revision),
         mock.call(DEPS_GIT, revision)])

  @mock.patch.object(GitilesRepository, 'GetSource', side_effect=[DEPS_CONTENT])
  def testNotChromiumRepo(self, mock_source):
    revision = 'abc'

    content = self.deps_downloader.Load('https://src.git', revision, 'DEPS')
    self.assertEqual(DEPS_CONTENT, content)
    mock_source.assert_called_once_with(DEPS, revision)

  @mock.patch.object(
      GitilesRepository, 'GetSource', side_effect=[None, DEPS_CONTENT])
  def testUseDEPSForNonexistentDEPS(self, mock_source):
    revision = 'abc'

    content = self.deps_downloader.Load('https://src.git', revision,
                                        'NONEXISTENT_DEPS')
    self.assertEqual(DEPS_CONTENT, content)
    mock_source.assert_has_calls(
        [mock.call('NONEXISTENT_DEPS', revision),
         mock.call(DEPS, revision)])

  @mock.patch.object(GitilesRepository, 'GetSource')
  def testUseSlaveDEPS(self, mock_source):
    revision = 'abc'
    expected_content = 'slave DEPS content'

    mock_source.side_effect = [expected_content]

    content = self.deps_downloader.Load('https://src.git', revision,
                                        'slave.DEPS')
    self.assertEqual(expected_content, content)
    mock_source.assert_called_once_with('slave.DEPS', revision)

  @mock.patch.object(GitilesRepository, 'GetSource', return_value=None)
  def testFailedToPullDEPSFile(self, _):

    self.assertRaisesRegexp(Exception, 'Failed to pull DEPS file.',
                            self.deps_downloader.Load, 'https://src.git', 'abc',
                            'DEPS')

  def testDEPSDownloaderForChromeVersion(self):

    def _MockGet(*_):
      return 200, base64.b64encode('Dummy DEPS content'), {}

    self.mock(HttpClientAppengine, '_Get', _MockGet)
    deps_downloader = chrome_dependency_fetcher.DEPSDownloader(
        gitiles_repository.GitilesRepository.Factory(HttpClientAppengine()))
    content = deps_downloader.Load('http://chrome-internal', '50.0.1234.0',
                                   'DEPS')
    self.assertEqual(content, 'Dummy DEPS content')

  def testGetDependency(self):
    src_path = 'src'
    src_repo_url = 'https://chromium.googlesource.com/chromium/src.git'
    src_revision = '123a'
    os_platform = 'unix'

    child1_dep = Dependency('src/a', 'https://a.git', '123a', 'DEPS')
    child2_dep = Dependency('src/b', 'https://b.git', '123b', 'DEPS')
    grand_child1 = Dependency('src/a/aa', 'https://aa.git', '123aa', 'DEPS')

    expected_dependency_dict = {
        'src/a': child1_dep,
        'src/b': child2_dep,
        'src/a/aa': grand_child1,
    }

    def DummyUpdateDependencyTree(root_dep, target_os_list, _):
      self.assertEqual(src_path, root_dep.path)
      self.assertEqual(src_repo_url, root_dep.repo_url)
      self.assertEqual(src_revision, root_dep.revision)
      self.assertEqual([os_platform], target_os_list)

      expected_dependency_dict[root_dep.path] = root_dep
      child1_dep.SetParent(root_dep)
      child2_dep.SetParent(root_dep)
      grand_child1.SetParent(child1_dep)

    self.mock(deps_parser, 'UpdateDependencyTree', DummyUpdateDependencyTree)

    dependency_dict = self.chrome_dep_fetcher.GetDependency(
        src_revision, os_platform)
    self.assertEqual(expected_dependency_dict, dependency_dict)

  def testGetDependencyForChromeVersion(self):
    src_path = 'src'
    src_repo_url = 'https://chromium.googlesource.com/chromium/src.git'
    os_platform = 'unix'

    child1_dep = Dependency('src/a', 'https://a.git', '123a', 'DEPS')
    child2_dep = Dependency('src/b', 'https://b.git', '123b', 'DEPS')
    grand_child1 = Dependency('src/a/aa', 'https://aa.git', '123aa', 'DEPS')

    expected_dependency_dict = {
        'src/a': child1_dep,
        'src/b': child2_dep,
        'src/a/aa': grand_child1,
    }

    def DummyUpdateDependencyTree(root_dep, target_os_list, _):
      self.assertEqual(src_path, root_dep.path)
      self.assertEqual(src_repo_url, root_dep.repo_url)
      self.assertEqual([os_platform], target_os_list)

      expected_dependency_dict[root_dep.path] = root_dep
      child1_dep.SetParent(root_dep)
      child2_dep.SetParent(root_dep)
      grand_child1.SetParent(child1_dep)

    self.mock(deps_parser, 'UpdateDependencyTree', DummyUpdateDependencyTree)

    dependency_dict = self.chrome_dep_fetcher.GetDependency(
        '50.0.1234.0', os_platform)
    self.assertEqual(expected_dependency_dict, dependency_dict)

  def testGetDependencyRolls(self):

    def MockGetDependency(revision, os_platform, _=False):
      self.assertEqual('unix', os_platform)
      if revision == 'rev2':
        return {
            'src':
                Dependency('src', 'https://url_src', 'rev2', 'DEPS'),
            'src/dep1':
                Dependency('src/dep1', 'https://url_dep1', '9', 'DEPS'),
            'src/dep2':
                Dependency('src/dep2', 'https://url_dep2', '5', 'DEPS'),
            'src/dep4':
                Dependency('src/dep4', 'https://url_dep4', '1', 'DEPS'),
        }
      else:
        self.assertEqual('rev1', revision)
        return {
            'src':
                Dependency('src', 'https://url_src', 'rev1', 'DEPS'),
            'src/dep1':
                Dependency('src/dep1', 'https://url_dep1', '7', 'DEPS'),
            'src/dep2':
                Dependency('src/dep2', 'https://url_dep2', '5', 'DEPS'),
            'src/dep3':
                Dependency('src/dep3', 'https://url_dep3', '3', 'DEPS'),
        }

    self.mock(self.chrome_dep_fetcher, 'GetDependency', MockGetDependency)

    expected_deps_rolls = [
        {
            'path': 'src/dep1',
            'repo_url': 'https://url_dep1',
            'old_revision': '7',
            'new_revision': '9',
        },
        {
            'path': 'src/dep4',
            'repo_url': 'https://url_dep4',
            'old_revision': None,
            'new_revision': '1',
        },
        {
            'path': 'src/dep3',
            'repo_url': 'https://url_dep3',
            'old_revision': '3',
            'new_revision': None,
        },
    ]

    deps_rolls = self.chrome_dep_fetcher.GetDependencyRolls(
        'rev1', 'rev2', 'unix')
    deps_rolls = [roll.ToDict() for roll in deps_rolls]
    deps_rolls.sort()
    expected_deps_rolls.sort()
    self.assertEqual(expected_deps_rolls, deps_rolls)

  def testGetDependencyRollsDict(self):

    def _MockGetDependencyRolls(old_revision, new_revision, *_, **kargs):
      dependency_rolls = [
          DependencyRoll('src/dep1', 'https://url_dep1', '7', '9'),
          DependencyRoll('src/dep2', 'https://url_dep2', '3', None)
      ]
      if not kargs['skip_chromium_roll']:
        dependency_rolls.append(
            DependencyRoll('src',
                           'https://chromium.googlesource.com/chromium/src.git',
                           old_revision, new_revision))

      return dependency_rolls

    self.mock(self.chrome_dep_fetcher, 'GetDependencyRolls',
              _MockGetDependencyRolls)

    expected_deps_rolls_skip_chromium = [
        DependencyRoll('src/dep1', 'https://url_dep1', '7', '9'),
        DependencyRoll('src/dep2', 'https://url_dep2', '3', None)
    ]
    self.assertEqual(
        self.chrome_dep_fetcher.GetDependencyRolls(
            '4', '5', 'all', skip_chromium_roll=True),
        expected_deps_rolls_skip_chromium)

    expected_deps_rolls_dict = {
        'src/dep1':
            DependencyRoll('src/dep1', 'https://url_dep1', '7', '9'),
        'src/dep2':
            DependencyRoll('src/dep2', 'https://url_dep2', '3', None),
        'src':
            DependencyRoll('src',
                           'https://chromium.googlesource.com/chromium/src.git',
                           '4', '5'),
    }
    self.assertEqual(
        self.chrome_dep_fetcher.GetDependencyRollsDict('4', '5', 'all'),
        expected_deps_rolls_dict)
