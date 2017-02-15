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
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
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
    script = blink_dir.join('Tools', 'Scripts', 'wpt-import')
    args = [
      '--auto-update',
      '--auth-refresh-token-json',
      '/creds/refresh_tokens/blink-w3c-test-autoroller',
      name,
    ]
    with api.step.context({'cwd': blink_dir}):
      api.python('update ' + name, script, args)
    git_cl_issue_link(api)

  with new_branch('update_wpt'):
    update_w3c_repo('wpt')
  with new_branch('update_css'):
    update_w3c_repo('css')


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
      api.test('w3c-test-autoroller') +
      api.properties(
          mastername='chromium.infra.cron',
          buildername='w3c-test-autoroller',
          slavename='fake-slave') +
      api.step_data(
          'git cl issue',
          api.json.output({
              'issue': 123456789,
              'issue_url': 'https://codereview.chromium.org/123456789'
          })) +
      api.step_data(
          'git cl issue (2)',
          api.json.output({
              'issue': 123456789,
              'issue_url': 'https://codereview.chromium.org/123456789'
          })))

  yield (
      api.test('w3c-test-autoroller-no-issue') +
      api.properties(
          mastername='chromium.infra.cron',
          buildername='w3c-test-autoroller',
          slavename='fake-slave') +
      api.step_data(
          'git cl issue',
          api.json.output({'issue': None, 'issue_url': None})) +
      api.step_data(
          'git cl issue (2)',
          api.json.output({'issue': None, 'issue_url': None})))
