# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A continuous builder which runs recipe tests."""

from recipe_engine.recipe_api import Property

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',

  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',

  'build/luci_config',
  'build/service_account',
]

PROPERTIES = {
  'project_under_test': Property(
      default='build', kind=str, help='luci-config project to run tests for'),
  'auth_with_account': Property(
      default=None, kind=str,
      help="Try to authenticate with given service account."),
}


def RunSteps(api, project_under_test, auth_with_account):
  if auth_with_account:
    api.luci_config.c.auth_token = api.service_account.get_token(
        auth_with_account)

  root_dir = api.path['start_dir']
  cache_dir = root_dir.join('_cache_dir')

  c = api.gclient.make_config(CACHE_DIR=cache_dir)
  soln = c.solutions.add()
  soln.name = project_under_test
  soln.url = api.luci_config.get_project_metadata(
      project_under_test)['repo_url']
  soln.revision = 'HEAD'

  api.bot_update.ensure_checkout(gclient_config=c, cwd=root_dir)

  # TODO(martiniss): allow recipes.cfg patches to take affect
  # This requires getting the refs.cfg from luci_config, reading the local
  # patched version, etc.
  result = api.luci_config.get_project_config(project_under_test, 'recipes.cfg')
  recipes_cfg = api.luci_config.parse_textproto(result['content'].split('\n'))
  path = recipes_cfg['recipes_path'][0].split('/')

  api.step(
      'recipe simulation test', [
          root_dir.join(*([project_under_test] + path + ['recipes.py'])),
          '--use-bootstrap', 'simulation_test'
      ])

def GenTests(api):
  yield (
      api.test('normal') +
      api.properties.generic(
          mastername='chromium.tools.build',
          buildername='recipe simulation tester',
          revision='deadbeaf',
          project_under_test='build',
      ) +
      api.luci_config.get_projects(('build',)) +
      api.luci_config.get_project_config(
          'build', 'recipes.cfg',
          'recipes_path: "foobar"')
  )

  yield (
      api.test('with_auth') +
      api.properties.generic(
          mastername='chromium.tools.build',
          buildername='recipe simulation tester',
          revision='deadbeaf',
          project_under_test='build',
          auth_with_account='build_limited',
      ) +
      api.luci_config.get_projects(('build',)) +
      api.luci_config.get_project_config(
          'build', 'recipes.cfg',
          'recipes_path: "foobar"')
  )
