# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Updates w3c tests automatically.

This recipe imports the latest changes to the w3c test repo and attempts
to upload and commit them if they pass on all commit queue try jobs
"""

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
]


def RunSteps(api):
    api.gclient.set_config('chromium')
    api.bot_update.ensure_checkout(force=True)

    api.git('config', 'user.name', 'W3C Autoroll Bot')
    api.git('config', 'user.email', 'w3c-test-updater-bot@chromium.org')

    cwd = api.path['checkout'].join('third_party', 'WebKit')

    api.python('update wpt',
               cwd.join('Tools', 'Scripts', 'update-w3c-deps'),
               ['--auto-update', 'wpt'],
               cwd=cwd)

    api.python('update wpt',
               cwd.join('Tools', 'Scripts', 'update-w3c-deps'),
               ['--auto-update', 'css'],
               cwd=cwd)


def GenTests(api):
  yield  (api.test('w3c-test-autoroller') +
          api.properties(mastername='chromium.infra.cron',
                         buildername='w3c-test-autoroller',
                         slavename='fake-slave'))
