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
  'recipe_engine/python',
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
  'force_build': Property(
      kind=bool, default=False,
      help=(
        'Forces building packages, even if they\'re available on the CIPD '
        'server already. Doing this disables uploads.')),
}


def RunSteps(api, package_locations, to_build, platform, force_build):
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

  _, unsupported = api.third_party_packages_ng.ensure_uploaded(
    to_build, platform, force_build)

  if unsupported:
    api.python.succeeding_step(
      '%d packges unsupported for %r' % (len(unsupported), platform),
      '<br/>' + '<br/>'.join(sorted(unsupported))
    )


def GenTests(api):
  def defaults():
    return (
      api.properties(package_locations=[
        {
          'repo': 'https://example.repo',
          'subdir': 'third_party_packages',
        }
      ]) +
      api.runtime(is_luci=True, is_experimental=False))

  yield api.test('basic') + defaults()

  pkgs = sorted(dict(
    pkg_a='''
    create { unsupported: true }
    upload { pkg_prefix: "prefix/deps" }
    ''',

    pkg_b='''
    create { unsupported: true }
    upload { pkg_prefix: "prefix/deps" }
    ''',
  ).items())

  test = (
    api.test('unsupported') + defaults() +
    api.step_data('load packages from desired repos.find package specs',
                  api.file.glob_paths([n+'/3pp.pb' for n, _ in pkgs]))
  )
  for pkg, spec in pkgs:
    test += api.step_data(
      "load packages from desired repos.load package specs.read '%s'" % pkg,
      api.file.read_text(spec))
  yield test
