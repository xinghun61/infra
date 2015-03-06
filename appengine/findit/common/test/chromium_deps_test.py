# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import unittest

from common import chromium_deps
from common import repository
from infra.libs.deps.dependency import Dependency


class DummyGitRepository(repository.Repository):
  RESPONSES = {}

  def __init__(self, *_):
    pass

  def GetSource(self, path, revision):
    return self.RESPONSES.get(path, {}).get(revision, None)


class ChromiumDEPSTest(unittest.TestCase):
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

    real_GitRepository = chromium_deps.git_repository.GitRepository
    try:
      chromium_deps.git_repository.GitRepository = DummyGitRepository

      content = chromium_deps.DEPSDownloader().Load(
          'https://src.git', revision, 'DEPS')
      self.assertEqual(expected_content, content)
    finally:
      chromium_deps.git_repository.GitRepository = real_GitRepository

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

    real_GitRepository = chromium_deps.git_repository.GitRepository
    try:
      chromium_deps.git_repository.GitRepository = DummyGitRepository

      content = chromium_deps.DEPSDownloader().Load(
          'https://src.git', revision, 'slave.DEPS')
      self.assertEqual(expected_content, content)
    finally:
      chromium_deps.git_repository.GitRepository = real_GitRepository

  def testFailedToPullDEPSFile(self):
    DummyGitRepository.RESPONSES = {}

    real_GitRepository = chromium_deps.git_repository.GitRepository
    try:
      chromium_deps.git_repository.GitRepository = DummyGitRepository

      deps_downloader = chromium_deps.DEPSDownloader()
      self.assertRaisesRegexp(Exception, 'Failed to pull DEPS file.',
                              deps_downloader.Load,
                              'https://src.git', 'abc', 'DEPS')
    finally:
      chromium_deps.git_repository.GitRepository = real_GitRepository

  def testGetChromeDependency(self):
    src_path = 'src/'
    src_repo_url = 'https://chromium.googlesource.com/chromium/src.git'
    src_revision = '123a'
    os_platform = ['unix']

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
      self.assertEqual(os_platform, target_os_list)

      expected_dependency_dict[root_dep.path] = root_dep
      child1_dep.SetParent(root_dep)
      child2_dep.SetParent(root_dep)
      grand_child1.SetParent(child1_dep)

    real_GetDependencyTree = chromium_deps.deps_parser.UpdateDependencyTree
    try:
      chromium_deps.deps_parser.UpdateDependencyTree = DummyUpdateDependencyTree

      dependency_dict = chromium_deps.GetChromeDependency(
          src_revision, os_platform)
      self.assertEqual(expected_dependency_dict, dependency_dict)
    finally:
      chromium_deps.deps_parser.UpdateDependencyTree = real_GetDependencyTree
