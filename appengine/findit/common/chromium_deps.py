# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from common import git_repository
from common import http_client_appengine
from infra.libs.deps import dependency
from infra.libs.deps import deps_parser


class DEPSDownloader(deps_parser.DEPSLoader):
  """Download DEPS from remote GIT repo."""

  def Load(self, repo_url, revision, deps_file):
    http_client = http_client_appengine.HttpClientAppengine()
    repo = git_repository.GitRepository(repo_url, http_client)

    content = None

    # Try .DEPS.git first if the given deps_file is "DEPS", because before
    # migration from SVN to GIT, .DEPS.git contains dependencies from GIT while
    # DEPS contains those from SVN.
    if deps_file == 'DEPS':
      content = repo.GetSource('.DEPS.git', revision)

    # If .DEPS.git is not found, use DEPS. Assume it is a commit after migration
    # from SVN to GIT.
    if content is None:
      content = repo.GetSource(deps_file, revision)
    else:
      return content

    if content is None:
      raise Exception('Failed to pull %s file.' % deps_file)
    else:
      return content


def GetChromeDependency(revision, os_platform):
  """Return all dependencies of Chrome as a dict for the given revision and os.

  Args:
    revision: The revision of a Chrome build.
    os_platform: The target platform of the Chrome build, should be one of
                 'win', 'ios', 'mac', 'unix', 'android', or 'all'.

  Returns:
    A map from component path to dependency.
  """
  root_dep = dependency.Dependency(
      'src/', 'https://chromium.googlesource.com/chromium/src.git', revision,
      'DEPS')

  deps_parser.UpdateDependencyTree(root_dep, os_platform, DEPSDownloader())

  dependencies = {}

  # Flatten the dependency tree into a one-level dict.
  def _FlattenDepTree(dep):
    dependencies[dep.path] = dep
    for child in dep.children.values():
      _FlattenDepTree(child)

  _FlattenDepTree(root_dep)

  return dependencies
