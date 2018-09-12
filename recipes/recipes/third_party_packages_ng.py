# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This recipe builds and packages third party software, such as Git."""

import hashlib

from recipe_engine.recipe_api import Property
from recipe_engine.config import ConfigList, ConfigGroup, Single, List


DEPS = [
  'recipe_engine/file',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/runtime',
  'recipe_engine/step',

  'depot_tools/git',

  'third_party_packages_ng',
]


PROPERTIES = {
  'package_locations': Property(
      help=('URL of repo containing package definitions.'
            'Cross-compiling requires docker on $PATH.'),
      kind=ConfigList(
        lambda: ConfigGroup(
          repo=Single(str),
          ref=Single(str, required=False),
          subdir=Single(str, required=False),
        ),
      )
  ),
  'to_build': Property(
    help=(
      'The names (and optionally versions) of the packages to build and upload.'
      ' Leave empty to build and upload all known packages. If you want to '
      'specify a version other than "latest", pass the package name like '
      '"some_package@1.3.4".'),
    kind=List(str),
    default=(),
  ),
  'platform': Property(
      kind=str, default=None,
      help=(
        'Target platform. Must be a valid CIPD ${platform}. Cross-compiling '
        'requires docker on $PATH.')),
}


def RunSteps(api, package_locations, to_build, platform):
  package_repos = api.path['cache'].join('builder')
  current_repos = set()
  try:
    current_repos = set(p.pieces[-1] for p in api.file.glob_paths(
      'read cached checkouts', package_repos, '*',
      test_data=[
        'deadbeef',
        'badc0ffe',
      ]
    ))
  except api.file.Error as err:  # pragma: no cover
    if err.errno_name != 'ENOENT':
      raise

  actual_repos = set()
  with api.step.nest('load packages from desired repos'):
    for pl in package_locations:
      repo = pl['repo']
      ref = pl.get('ref', 'refs/heads/master')
      subdir = pl.get('subdir', '')

      hash_name = hashlib.sha1("%s:%s" % (repo, ref)).hexdigest()
      actual_repos.add(hash_name)

      checkout_path = package_repos.join(hash_name)
      api.git.checkout(
        repo, ref, checkout_path, submodules=False)

      if subdir:
        checkout_path = checkout_path.join(*subdir.split('/'))
      api.third_party_packages_ng.load_packages_from_path(checkout_path)

  with api.step.nest('remove unused repos'):
    leftovers = current_repos - actual_repos
    for hash_name in leftovers:
      api.file.rmtree('rm %s' % (hash_name,),
                      package_repos.join(hash_name))

  api.third_party_packages_ng.ensure_uploaded(to_build, platform)


def GenTests(api):
  yield (
      api.test('basic') +
      api.properties(package_locations=[
        {
          'repo': 'https://example.repo',
          'subdir': 'third_party_packages',
        }
      ]) +
      api.runtime(is_luci=True, is_experimental=False))
