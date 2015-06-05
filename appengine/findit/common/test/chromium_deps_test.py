# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

from testing_utils import testing

from common import chromium_deps
from common import deps_parser
from common import git_repository
from common import repository
from common.dependency import Dependency


class DummyGitRepository(repository.Repository):
  RESPONSES = {}

  def __init__(self, *_):
    pass

  def GetSource(self, path, revision):
    return self.RESPONSES.get(path, {}).get(revision, None)


class ChromiumDEPSTest(testing.AppengineTestCase):
  DEPS_GIT = '.DEPS.git'
  DEPS = 'DEPS'

  def testUseDEPS_GIT(self):
    revision = 'abc'
    expected_content = '.DEPS.git content'

    DummyGitRepository.RESPONSES = {
        self.DEPS_GIT: {
            revision: expected_content
        },
        self.DEPS: {
            revision: 'DEPS test'
        },
    }

    self.mock(git_repository, 'GitRepository', DummyGitRepository)

    content = chromium_deps.DEPSDownloader(check_deps_git_first=True).Load(
        'https://src.git', revision, 'DEPS')
    self.assertEqual(expected_content, content)

  def testNotUseDEPS_GIT(self):
    revision = 'abc'
    expected_content = 'DEPS test'

    DummyGitRepository.RESPONSES = {
        self.DEPS_GIT: {
            revision: '.DEPS.git content'
        },
        self.DEPS: {
            revision: expected_content
        },
    }

    self.mock(git_repository, 'GitRepository', DummyGitRepository)

    content = chromium_deps.DEPSDownloader(check_deps_git_first=False).Load(
        'https://src.git', revision, 'DEPS')
    self.assertEqual(expected_content, content)

  def testUseSlaveDEPS(self):
    revision = 'abc'
    expected_content = 'slave DEPS content'

    DummyGitRepository.RESPONSES = {
        self.DEPS_GIT: {
            revision: '.DEPS.git content'
        },
        'slave.DEPS': {
            revision: expected_content
        },
    }

    self.mock(git_repository, 'GitRepository', DummyGitRepository)

    content = chromium_deps.DEPSDownloader(check_deps_git_first=True).Load(
        'https://src.git', revision, 'slave.DEPS')
    self.assertEqual(expected_content, content)

  def testFailedToPullDEPSFile(self):
    DummyGitRepository.RESPONSES = {}

    self.mock(git_repository, 'GitRepository', DummyGitRepository)

    deps_downloader = chromium_deps.DEPSDownloader()
    self.assertRaisesRegexp(Exception, 'Failed to pull DEPS file.',
                            deps_downloader.Load,
                            'https://src.git', 'abc', 'DEPS')

  def testGetChromeDependency(self):
    src_path = 'src/'
    src_repo_url = 'https://chromium.googlesource.com/chromium/src.git'
    src_revision = '123a'
    os_platform = 'unix'

    child1_dep = Dependency('src/a/', 'https://a.git', '123a', 'DEPS')
    child2_dep = Dependency('src/b/', 'https://b.git', '123b', 'DEPS')
    grand_child1 = Dependency('src/a/aa/', 'https://aa.git', '123aa', 'DEPS')

    expected_dependency_dict = {
        'src/a/': child1_dep,
        'src/b/': child2_dep,
        'src/a/aa/': grand_child1,
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

    dependency_dict = chromium_deps.GetChromeDependency(
        src_revision, os_platform)
    self.assertEqual(expected_dependency_dict, dependency_dict)

  def testGetChromiumDEPSRolls(self):
    def MockGetChromeDependency(revision, os_platform, _=False):
      self.assertEqual('unix', os_platform)
      if revision == 'rev2':
        return {
            'src/': Dependency('src/', 'https://url_src', 'rev2', 'DEPS'),
            'src/dep1': Dependency('src/dep1', 'https://url_dep1', '9', 'DEPS'),
            'src/dep2': Dependency('src/dep2', 'https://url_dep2', '5', 'DEPS'),
            'src/dep4': Dependency('src/dep4', 'https://url_dep4', '1', 'DEPS'),
        }
      else:
        self.assertEqual('rev1', revision)
        return {
            'src/': Dependency('src/', 'https://url_src', 'rev1', 'DEPS'),
            'src/dep1': Dependency('src/dep1', 'https://url_dep1', '7', 'DEPS'),
            'src/dep2': Dependency('src/dep2', 'https://url_dep2', '5', 'DEPS'),
            'src/dep3': Dependency('src/dep3', 'https://url_dep3', '3', 'DEPS'),
        }

    self.mock(chromium_deps, 'GetChromeDependency', MockGetChromeDependency)

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

    deps_rolls = chromium_deps.GetChromiumDEPSRolls('rev1', 'rev2', 'unix')
    self.assertEqual(expected_deps_rolls,
                     [roll.ToDict() for roll in deps_rolls])
