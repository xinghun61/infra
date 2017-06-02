# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/infra_paths',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]


def RunSteps(api):
  api.gclient.set_config('infradata_master_manager')
  api.bot_update.ensure_checkout(
      patch_root='infra-data-master-manager', patch_oauth2=True,
      use_site_config_creds=False)
  api.gclient.runhooks()

  api.python('master manager configuration test',
             api.path['start_dir'].join('infra', 'run.py'),
             ['infra.services.master_manager_launcher',
              '--verify',
              '--ts-mon-endpoint=none',
              '--json-file',
             api.path['start_dir'].join(
                 'infra-data-master-manager',
                 'desired_master_state.json')])


def GenTests(api):
  yield (
      api.test('master_manager_config') +
      api.properties.git_scheduled(
          buildername='infradata_config',
          buildnumber=123,
          mastername='internal.infra',
          repository='https://chrome-internal.googlesource.com/infradata'))
  yield (
      api.test('master_manager_config_patch') +
      api.properties.git_scheduled(
          buildername='infradata_config',
          buildnumber=123,
          mastername='internal.infra.try',
          patch_project='infra-data-configs',
          repository='https://chrome-internal.googlesource.com/infradata'))
