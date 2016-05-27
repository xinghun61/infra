# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
  'cipd',
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/path',
]


PROPERTIES = {
  'mastername': Property(default=''),
  'buildername': Property(default=''),
  'buildnumber': Property(default=-1, kind=int),
}

def RunSteps(api, mastername, buildername, buildnumber):
  api.gclient.set_config('recipes_py_bare')
  bot_update_step = api.bot_update.ensure_checkout(force=True)

  tags = {
    'buildbot_build' : '%s/%s/%s' % (mastername, buildername, buildnumber),
    'git_repository' : api.gclient.c.solutions[0].url,
    'git_revision' : bot_update_step.presentation.properties['got_revision'],
  }

  api.cipd.install_client()
  api.cipd.create(
      api.path['checkout'].join('infra', 'cipd', 'recipes-py.yaml'),
      tags=tags)


def GenTests(api):
  yield api.test('basic')
