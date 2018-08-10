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

  chopsui_test_path = api.path['checkout'].join(
      'crdx', 'chopsui')
  api.wct.run(chopsui_test_path, 'test/', 'ChOpsUI WCT Tests')

  monorail_test_path = api.path['checkout'].join(
      'appengine', 'monorail')
  api.wct.run(monorail_test_path, 'elements/test', 'Monorail WCT Tests')

  som_test_path = api.path['checkout'].join(
      'go', 'src', 'infra', 'appengine', 'sheriff-o-matic', 'frontend')
  api.wct.run(som_test_path, 'test/', 'SoM WCT Tests')


def GenTests(api):
  yield api.test('basic')
  yield api.test('not-linux') + api.platform('win', 32)
  yield api.test('has package.json') + api.path.exists(
      api.path['checkout'].join('appengine', 'monorail', 'package.json'))
