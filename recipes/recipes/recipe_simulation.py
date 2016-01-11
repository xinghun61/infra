# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A continious builder for build repo which simulates recipes."""

DEPS = [
  'bot_update',
  'gclient',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/step',
]


def RunSteps(api):
  api.gclient.set_config('build')
  api.bot_update.ensure_checkout(force=True)
  recipes_py = api.path['checkout'].join('scripts', 'slave', 'recipes.py')
  api.step('recipe fetch deps', [recipes_py, 'fetch'])
  api.step('recipe simulation test', [recipes_py, 'simulation_test'])


def GenTests(api):
  yield (
      api.test('normal') +
      api.properties.generic(
          mastername='chromium.tools.build',
          buildername='recipe simulation tester',
          revision='deadbeaf',
      )
  )
