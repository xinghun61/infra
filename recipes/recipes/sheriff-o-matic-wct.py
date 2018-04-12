# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/step',
  'wct',
]

def RunSteps(api):
  project_name = 'infra'

  api.gclient.set_config(project_name)
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()

  api.wct.install()
  test_path = api.path['checkout'].join(
      'go', 'src', 'infra', 'appengine', 'sheriff-o-matic', 'frontend')

  api.wct.run(test_path)

def GenTests(api):
  yield api.test('basic')
  yield api.test('not-linux') + api.platform('win', 32)
