# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property
from recipe_engine.config import List

DEPS = [
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/step',

  'depot_tools/cipd',
]

PROPERTIES = {
  'recipe_bundler_pkg': Property(
    kind=str, help='The CIPD package to fetch the recipe bundler from',
    default='infra/tools/luci/recipe_bundler/${platform}',
  ),
  'recipe_bundler_vers': Property(
    kind=str, help='The version of the recipe_bundler CIPD package to fetch',
  ),

  'repo_specs': Property(
    kind=List(str),
    help=('The list of repo specs to process, as defined by recipe_bundler\'s '
          '"-r" flag.'),
    default=[]
  ),

  'repo_specs_optional': Property(
    kind=List(str),
    help=('Like "repo_specs", but it\'s not an error if any these fail.'),
    default=[]
  ),

  'package_name_prefix': Property(
    kind=str, help='The CIPD package prefix for non-internal recipes',
  ),

  'package_name_internal_prefix': Property(
    kind=str, help='The CIPD package prefix for internal recipes',
  ),
}


def RunSteps(api, recipe_bundler_pkg, recipe_bundler_vers, repo_specs,
             repo_specs_optional, package_name_prefix,
             package_name_internal_prefix):
  bundler_path = api.path['cache'].join('builder', 'bundler')
  api.cipd.ensure(bundler_path, {
    recipe_bundler_pkg: recipe_bundler_vers,
  })

  cmd = [
    bundler_path.join('recipe_bundler'),
    'bundle',
    '-log-level', 'debug',
    '-workdir', api.path['cache'].join('builder', 'workdir'),
    '-package-name-prefix', package_name_prefix,
    '-package-name-internal-prefix', package_name_internal_prefix,
  ]

  if repo_specs:
    args = []
    for spec in repo_specs:
      args += ['-r', spec]
    api.step('run recipe_bundler', cmd + args)

  if repo_specs_optional:
    args = []
    for spec in repo_specs_optional:
      args += ['-r', spec]
    # TODO(mmoss): If bundling fails, set a "Warning" step result rather than
    # just ignoring the errors? Requires crbug.com/854099.
    api.step('run optional recipe_bundler', cmd + args, ok_ret='any')


def GenTests(api):
  yield api.test('basic') + api.properties(
    recipe_bundler_vers='latest',
    repo_specs=[
      'chromium.googlesource.com/chromium/tools/build',
      'chromium.googlesource.com/infra/infra',
    ],
    package_name_prefix='infra/recipe_bundles',
    package_name_internal_prefix='infra_internal/recipe_bundles',
  )

  yield api.test('basic_optional') + api.properties(
    recipe_bundler_vers='latest',
    repo_specs_optional=[
      'chromium.googlesource.com/chromium/tools/build:'
      'FETCH_HEAD,refs/heads/maybe/bogus',
    ],
    package_name_prefix='infra/recipe_bundles',
    package_name_internal_prefix='infra_internal/recipe_bundles',
  ) + api.step_data('run optional recipe_bundler', retcode=1)
