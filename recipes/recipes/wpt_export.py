# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Exports commits in Chromium to the web-platform-tests repo.

This recipe runs the wpt-export script; it is expected to be run as a
recurring job at a short interval. It creates pull requests on GitHub
for Chromium commits that contain exportable changes, merges these
pull requests.

See: //docs/testing/web_platform_tests.md (https://goo.gl/rSRGmZ)
"""

import contextlib

DEPS = [
  'build/chromium',
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
]


def RunSteps(api):
  api.gclient.set_config('chromium')
  api.bot_update.ensure_checkout()
  api.git('config', '--global', 'user.name',
          'Chromium WPT Sync',
          name='set git config user.name')
  api.git('config', '--global', 'user.email',
          'blink-w3c-test-autoroller@chromium.org',
          name='set git config user.email')

  script = api.path['checkout'].join('third_party', 'WebKit', 'Tools',
                                     'Scripts', 'wpt-export')
  args = [
    '--credentials-json',
    '/creds/github/wpt-export.json',
  ]
  api.python('Export Chromium commits and in-flight CLs to WPT', script, args)


def GenTests(api):
  yield (
      api.test('wpt-export') +
      api.properties(
          mastername='chromium.infra.cron',
          buildername='wpt-export',
          slavename='fake-slave') +
      api.step_data('create PR or merge in-flight PR'))
