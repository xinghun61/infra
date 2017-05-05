# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Looks for exportable commits and exports them to GitHub.

Runs the web-platform-tests exporter. The exporter expects to be run as a
recurring job at a short interval. Each iteration, it will do one of two
things:

1. If an in-flight PR in the WPT repo exists, merge it.
2. Pull Chromium and WPT, find the earliest exportable commit since the
   last WPT export, and create a PR on GitHub for it.

More details in the script at third_party/WebKit/Tools/Scripts/wpt-export.
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
  api.git('config', 'user.name', 'Chromium WPT Sync',
          name='set git config user.name')
  api.git('config', 'user.email', 'blink-w3c-test-autoroller@chromium.org',
          name='set git config user.email')

  script = api.path['checkout'].join('third_party', 'WebKit', 'Tools',
                                     'Scripts', 'wpt-export')
  args = [
    '--github-credentials-json',
    '/creds/github/wpt-export.json',
  ]
  api.python('create PR or merge in-flight PR', script, args)


def GenTests(api):
  yield (
      api.test('wpt-export') +
      api.properties(
          mastername='chromium.infra.cron',
          buildername='wpt-export',
          slavename='fake-slave') +
      api.step_data('create PR or merge in-flight PR'))
