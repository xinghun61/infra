# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from common import dependency
from common import deps_parser
from common import git_repository
from common import http_client_appengine


_CHROMIUM_ROOT_DIR = 'src/'
_CHROMIUM_REPO_MASTER = 'https://chromium.googlesource.com/chromium/src.git'

_CHROME_VERSION_PATTERN = re.compile(r'^\d+\.\d+\.\d+\.\d+$')

_BUILDSPEC_REPO = ('https://chrome-internal.googlesource.com/chrome/tools/'
                   'buildspec.git/')


def IsChromeVersion(revision):
  """Determines if a revision is a chrome version."""
  if _CHROME_VERSION_PATTERN.match(revision):
    return True

  return False


class DEPSDownloader(deps_parser.DEPSLoader):
  """Downloads DEPS from remote Git repo."""

  def Load(self, repo_url, revision, deps_file):
    http_client = http_client_appengine.HttpClientAppengine()
    repo = git_repository.GitRepository(repo_url, http_client)

    content = None
    if deps_file == 'DEPS' and repo_url == _CHROMIUM_REPO_MASTER:
      # Try .DEPS.git instead of DEPS first, for commits during the Git chaos.
      content = repo.GetSource('.DEPS.git', revision)

    if content is None:
      content = repo.GetSource(deps_file, revision)

    if content is None and deps_file != 'DEPS':
      # Like gclient, fall back to raw 'DEPS' when all else fails.
      content = repo.GetSource('DEPS', revision)

    if content is None:
      raise Exception(
          'Failed to pull %s file from %s, at revision %s.' % (
              deps_file, repo_url, revision))

    return content


def GetChromeDependency(revision, platform):
  """Returns all dependencies of Chrome as a dict for the given revision and OS.

  Args:
    revision (str): The revision of a Chrome build, it can be a githash or a
      chrome version for a official build.
    platform (str): The target platform of the Chrome build, should be one of
      'win', 'ios', 'mac', 'unix', 'android', or 'all'.

  Returns:
    A map from dependency path to the dependency info.
  """
  deps_repo_info = {'deps_file': 'DEPS'}

  if IsChromeVersion(revision):
    # For chrome version, get the DEPS file from internal buildspec/ repo
    # instead of chromium trunk.
    deps_repo_info['deps_repo_url'] = _BUILDSPEC_REPO
    deps_repo_info['deps_repo_revision'] = 'master'
    deps_repo_info['deps_file'] = 'releases/%s/DEPS' % revision

  root_dep = dependency.Dependency(
      _CHROMIUM_ROOT_DIR, _CHROMIUM_REPO_MASTER, revision, **deps_repo_info)

  deps_parser.UpdateDependencyTree(
      root_dep, [platform], DEPSDownloader())

  dependencies = {}

  # Flatten the dependency tree into a one-level dict.
  def FlattenDepTree(dep):
    dependencies[dep.path] = dep
    for child in dep.children.values():
      FlattenDepTree(child)

  FlattenDepTree(root_dep)

  # Make sure that DEPS file in buildspec/ overwrite the chromium repo.
  dependencies[_CHROMIUM_ROOT_DIR] = root_dep

  return dependencies


def GetChromiumDEPSRolls(old_cr_revision, new_cr_revision, platform,
                         skip_chromium_roll=True):
  """Returns a list of dependency rolls between the given Chromium revisions.

  Args:
    old_cr_revision (str): The old Chromium revision, it can be a githash or a
      chrome version for a official build.
    new_cr_revision (str): The new Chromium revision, it can be a githash or a
      chrome version for a official build.
    platform (str): The target OS platform of the Chrome or test binary.
    skip_chromium_roll (bool): If False, chromium roll will be contained in
      the return.

  Returns:
    A list of DependencyRoll objects in the revision range.
  """
  old_deps = GetChromeDependency(
      old_cr_revision, platform)
  new_deps = GetChromeDependency(
      new_cr_revision, platform)

  rolls = []

  for path, new_dep in new_deps.iteritems():
    if skip_chromium_roll and path == _CHROMIUM_ROOT_DIR:
      continue

    old_revision = None
    if path in old_deps:
      old_revision = old_deps[path].revision

    if old_revision != new_dep.revision:
      rolls.append(
          dependency.DependencyRoll(
              path, new_dep.repo_url, old_revision, new_dep.revision))

  for path, old_dep in old_deps.iteritems():
    if path not in new_deps:
      rolls.append(
          dependency.DependencyRoll(
              path, old_dep.repo_url, old_dep.revision, None))

  return rolls


def GetDEPSRollsDict(old_cr_revision, new_cr_revision, platform):
  """Gets dep_path to DependencyRoll dictionary for deps between revisions.

  Args:
    old_cr_revision (str): The old Chromium revision, it can be a githash or a
      chrome version for a official build.
    new_cr_revision (str): The new Chromium revision, it can be a githash or a
      chrome version for a official build.
    platform (str): The target OS platform of the Chrome or test binary.

  Returns:
    A dict, mapping dep path to its DependencyRoll.
  """
  deps_rolls = GetChromiumDEPSRolls(old_cr_revision, new_cr_revision, platform,
                                    skip_chromium_roll=False)

  deps_rolls_dict = {}

  for dep_roll in deps_rolls:
    deps_rolls_dict[dep_roll.path] = dep_roll

  return deps_rolls_dict
