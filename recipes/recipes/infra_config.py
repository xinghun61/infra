# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'bot_update',
  'file',
  'gclient',
  'json',
  'path',
  'platform',
  'properties',
  'python',
  'step',
]


def GenSteps(api):
  api.gclient.set_config('infradata_config_internal')
  api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()

  api.python('master manager configuration test',
             api.path['slave_build'].join('infra', 'run.py'),
             ['infra.services.master_manager_launcher',
             '--verify',
             '--json-file',
             api.path['slave_build'].join(
                 'infradata_config',
                 'master-manager',
                 'desired_master_state.json')])


def GenTests(api):
  yield (
      api.test('infradata_config') +
      api.properties.git_scheduled(
          buildername='infradata_config',
          buildnumber=123,
          mastername='internal.infra',
          repository='https://chrome-internal.googlesource.com/infradata'))
