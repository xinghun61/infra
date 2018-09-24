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
  'recipe_engine/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/runtime',
  'recipe_engine/step',
]


def RunSteps(api):
  api.gclient.set_config('chromium')
  api.bot_update.ensure_checkout()
  api.git('config', 'user.name', 'Chromium WPT Sync',
          name='set git config user.name')
  api.git('config', 'user.email', 'blink-w3c-test-autoroller@chromium.org',
          name='set git config user.email')
  blink_dir = api.path['checkout'].join('third_party', 'blink')

  # Set up a dummy HOME to avoid being affected by GCE default creds.
  @contextlib.contextmanager
  def create_dummy_home():
    temp_home = None
    try:
      temp_home = api.path.mkdtemp('home')
      api.file.copy('copy credentials to dummy HOME',
                    api.path.expanduser('~/.netrc'),
                    api.path.join(temp_home, '.netrc'))
      # This global config must be set; otherwise, `git cl` will complain.
      with api.context(cwd=temp_home):
        api.git('config', '--global', 'http.cookiefile',
                api.path.join(temp_home, '.gitcookies'),
                name='set git config http.cookiefile in dummy HOME')
      yield temp_home
    finally:
      if temp_home:
        api.file.rmtree('rmtree dummy HOME', temp_home)

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
    script = blink_dir.join('tools', 'wpt_import.py')
    args = [
      '--credentials-json',
      '/creds/json/wpt-import.json',
    ]
    # TODO(robertma): Drop the experimental branch when migration is completed.
    if api.runtime.is_experimental:
      args.append('--verbose')
    else:
      args += [
        '--auto-update',
        '--auto-file-bugs',
      ]

    # BuildBot only, as the service account on LUCI has the right permissions.
    if not api.runtime.is_luci:
      args += [
        '--auth-refresh-token-json',
        '/creds/refresh_tokens/blink-w3c-test-autoroller',
        '--monorail-auth-json',
        '/creds/service_accounts/service-account-wpt-monorail-api.json',
      ]

    try:
      if api.runtime.is_luci:
        with api.context(cwd=blink_dir):
          api.python('Import changes from WPT to Chromium', script, args,
                     venv=True)
      else:
        # Prevent BuildBot from using the default GCE service account.
        with create_dummy_home() as temp_home:
          with api.context(cwd=blink_dir,
                           # Override GCE creds detection of git-cl.
                           env={'SKIP_GCE_AUTH_FOR_GIT': '1',
                                'HOME': temp_home}):
            api.python('Import changes from WPT to Chromium', script, args,
                       venv=True)
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
      api.test('wpt-import-without-issue_luci') +
      api.properties(
          mastername='chromium.infra.cron',
          buildername='wpt-importer',
          slavename='fake-slave') +
      api.runtime(is_luci=True, is_experimental=False) +
      api.step_data(
          'git cl issue',
          api.json.output({'issue': None, 'issue_url': None})))

  yield (
      api.test('wpt-import-without-issue_buildbot_experimental') +
      api.properties(
          mastername='chromium.infra.cron',
          buildername='wpt-importer',
          slavename='fake-slave') +
      api.runtime(is_luci=False, is_experimental=True) +
      api.step_data(
          'git cl issue',
          api.json.output({'issue': None, 'issue_url': None})))
