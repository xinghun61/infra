# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
]


def RunSteps(api):
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()
  json_test_data = {'foo.cfg': 'bar\nbaz'}
  with api.context(cwd=api.path['checkout']):
    result = api.python(
        'Run checks', 'run.py',
        ['infra.tools.luci_check', '--output-json', api.json.output()],
        step_test_data=(lambda: api.json.test_api.output(json_test_data)))
  if result and result.json.output:
    for name, data in result.json.output.iteritems():
      result.presentation.logs[name] = data.split('\n')


def GenTests(api):
  yield (
    api.test('luci_check')
  )
