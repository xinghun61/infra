# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/cipd',
  'depot_tools/gclient',
  'recipe_engine/buildbucket',
  'recipe_engine/path',
  'recipe_engine/properties',
]


def RunSteps(api):
  api.cipd.set_service_account_credentials(
      api.cipd.default_bot_service_account_credentials)

  api.gclient.set_config('recipes_py_bare')
  bot_update_step = api.bot_update.ensure_checkout()

  tags = {
    'buildbucket_id': str(api.buildbucket.build.id),
    'git_repository': api.gclient.c.solutions[0].url,
    'git_revision': bot_update_step.presentation.properties['got_revision'],
  }

  api.cipd.create_from_yaml(
      api.path['checkout'].join('infra', 'cipd', 'recipes-py.yaml'),
      refs=['latest'],
      tags=tags)


def GenTests(api):
  yield api.test('basic') + api.properties(path_config='kitchen')
