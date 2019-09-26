# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/step',
]


def RunSteps(api):
  api.gclient.set_config('luci_py')
  api.bot_update.ensure_checkout()
  # TODO(tandrii): trigger tests without PRESUBMIT.py; https://crbug.com/917479

  if api.platform.is_linux:
    RunSwarmingUITests(api)


def RunSwarmingUITests(api):
  ui_dir = api.path['checkout'].join('luci', 'appengine', 'swarming', 'ui2')
  node_path = ui_dir.join('nodejs', 'bin')
  paths_to_add = [api.path.pathsep.join([str(node_path)])]
  env_prefixes = {'PATH': paths_to_add}
  with api.context(env_prefixes=env_prefixes, cwd=ui_dir):
    api.step('swarming-ui install node modules', ['npm', 'ci'])
    api.step('swarming-ui run tests', ['make', 'test'])


def GenTests(api):
  yield (
      api.test('ci') +
      api.buildbucket.ci_build(
          'infra', 'ci', 'Luci-py linux-64',
          git_repo='https://chromium.googlesource.com/infra/luci/luci-py',
      )
  )

  yield (
      api.test('try') +
      api.buildbucket.try_build(
          'infra', 'try', 'Luci-py Presubmit',
          git_repo='https://chromium.googlesource.com/infra/luci/luci-py',
      )
  )
