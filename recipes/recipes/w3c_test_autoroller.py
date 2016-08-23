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
    RIETVELD_REFRESH_TOKEN = '/creds/refresh_tokens/blink-w3c-test-autoroller'
    api.gclient.set_config('chromium', GIT_MODE=True)
    api.bot_update.ensure_checkout(force=True)

    api.git('config', 'user.name', 'Blink W3C Test Autoroller')
    api.git('config', 'user.email', 'blink-w3c-test-autoroller@chromium.org')
    api.git('checkout', '-B', 'update_w3c_tests')

    cwd = api.path['checkout'].join('third_party', 'WebKit')

    api.python('update wpt',
               cwd.join('Tools', 'Scripts', 'update-w3c-deps'),
               ['--auto-update', 'wpt',
                '--auth-refresh-token-json', RIETVELD_REFRESH_TOKEN],
               cwd=cwd)

    api.python('update css',
               cwd.join('Tools', 'Scripts', 'update-w3c-deps'),
               ['--auto-update', 'css',
                '--auth-refresh-token-json', RIETVELD_REFRESH_TOKEN],
               cwd=cwd)


def GenTests(api):
  yield  (api.test('w3c-test-autoroller') +
          api.properties(mastername='chromium.infra.cron',
                         buildername='w3c-test-autoroller',
                         slavename='fake-slave'))
