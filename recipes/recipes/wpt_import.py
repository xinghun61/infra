# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Imports changes from web-platform-tests into Chromium.

This recipe runs the wpt-import script. The import process involves
first fetching the latest changes from web-platform-tests, then running
the tests via try jobs and and updating any baselines and expectations,
before committing to Chromium.

See: //docs/testing/web_platform_tests.md (https://goo.gl/rSRGmZ)
"""

import contextlib

DEPS = [
  'build/chromium',
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]


def RunSteps(api):
  api.gclient.set_config('chromium')
  api.bot_update.ensure_checkout()
  api.git('config', 'user.name', 'Chromium WPT Sync',
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

  with new_branch('update_wpt'):
    script = blink_dir.join('Tools', 'Scripts', 'wpt-import')
    args = [
      '--auto-update',
      '--auth-refresh-token-json',
      '/creds/refresh_tokens/blink-w3c-test-autoroller',
      '--credentials-json',
      '/creds/json/wpt-import.json',
    ]
    try:
      with api.context(cwd=blink_dir):
        api.python('Import changes from WPT to Chromium', script, args)
    finally:
      git_cl_issue_link(api)


def git_cl_issue_link(api):
  """Runs a step which adds a link to the current CL if there is one."""
  issue_step = api.m.git(
      'cl', 'issue', '--json', api.json.output(),
      name='git cl issue')
  issue_result = issue_step.json.output
  if not issue_result or not issue_result.get('issue_url'):
      return
  link_text = 'issue %s' % issue_result['issue']
  issue_step.presentation.links[link_text] = issue_result['issue_url']


def GenTests(api):
  yield (
      api.test('wpt-import-with-issue') +
      api.properties(
          mastername='chromium.infra.cron',
          buildername='wpt-importer',
          slavename='fake-slave') +
      api.step_data(
          'git cl issue',
          api.json.output({
              'issue': 123456789,
              'issue_url': 'https://codereview.chromium.org/123456789'
          })))

  yield (
      api.test('wpt-import-without-issue') +
      api.properties(
          mastername='chromium.infra.cron',
          buildername='wpt-importer',
          slavename='fake-slave') +
      api.step_data(
          'git cl issue',
          api.json.output({'issue': None, 'issue_url': None})))
