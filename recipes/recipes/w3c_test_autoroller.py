# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Updates w3c tests automatically.

This recipe imports the latest changes to the w3c test repo and attempts
to upload and commit them if they pass on all commit queue try jobs
"""

import contextlib

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
  api.bot_update.ensure_checkout()
  api.git('config', 'user.name', 'Blink W3C Test Autoroller',
          name='set git config user.name')
  api.git('config', 'user.email', 'blink-w3c-test-autoroller@chromium.org',
          name='set git config user.email')
  blink_dir = api.path['checkout'].join('third_party', 'WebKit')

  @contextlib.contextmanager
  def new_branch(name):
    def delete_branch(name):
      # Get off branch, if any, otherwise delete fails.
      api.git('checkout', 'origin/master')
      api.git('branch', '-D', name, ok_ret='any')
    delete_branch(name)
    api.git.new_branch(name)
    try:
      yield
    finally:
      delete_branch(name)

  def update_w3c_repo(name):
    script = blink_dir.join('Tools', 'Scripts', 'update-w3c-deps')
    args = [
      '--auto-update',
      '--auth-refresh-token-json',
      '/creds/refresh_tokens/blink-w3c-test-autoroller',
      name,
    ]
    api.python('update ' + name, script, args, cwd=blink_dir)

  with new_branch('update_wpt'):
    update_w3c_repo('wpt')
  with new_branch('update_css'):
    update_w3c_repo('css')


def GenTests(api):
  yield (api.test('w3c-test-autoroller') +
         api.properties(mastername='chromium.infra.cron',
                        buildername='w3c-test-autoroller',
                        slavename='fake-slave'))
