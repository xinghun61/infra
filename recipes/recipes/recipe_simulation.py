# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A continious builder for build repo which simulates recipes."""

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
]


def RunSteps(api):
  api.gclient.set_config('build')
  api.bot_update.ensure_checkout(force=True)
  recipes_py = api.path['checkout'].join('scripts', 'slave', 'recipes.py')
  api.python('recipe fetch deps', recipes_py, ['fetch'])
  # In theory, this should work too. But in practice, this fails to import
  # coverage module (http://crbug.com/577049).
  # api.python('recipe simulation test', recipes_py, ['simulation_test'])
  recipe_simulation_test = api.path['checkout'].join(
      'scripts', 'slave', 'unittests', 'recipe_simulation_test.py')
  api.python('recipe simulation test', recipe_simulation_test, ['test'])


def GenTests(api):
  yield (
      api.test('normal') +
      api.properties.generic(
          mastername='chromium.tools.build',
          buildername='recipe simulation tester',
          revision='deadbeaf',
      )
  )
