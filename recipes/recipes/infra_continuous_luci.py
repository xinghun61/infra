# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Builds and tests infra.git code.

Very dumb for now, with no side effects. Runs continuously on LUCI in both
staging and prod environments.
"""


DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/context',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]


def RunSteps(api):
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()

  with api.step.defer_results():
    with api.context(cwd=api.path['checkout']):
      api.python(
          'infra python tests',
          'test.py',
          ['test', '--jobs', 1])

    api.python(
        'go third parties',
        api.path['checkout'].join('go', 'env.py'),
        ['go', 'version'])

    api.python(
        'infra go tests',
        api.path['checkout'].join('go', 'env.py'),
        ['python', api.path['checkout'].join('go', 'test.py')])


def GenTests(api):
  yield api.test('default')
