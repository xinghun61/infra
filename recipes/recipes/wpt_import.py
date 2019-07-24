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
  'cloudkms',

  'build/chromium',
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/git_cl',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/runtime',
]


# The credentials JSON is encrypted with KMS_CRYPTO_KEY and then stored in
# assets/CREDS_NAME.
# See the following comment for how to update the credentials:
# https://cs.chromium.org/chromium/infra/recipes/recipes/remote_execute_dataflow_workflow.py?l=72&rcl=7bc161db4cc3c89acb8577c25011f5c0758e5956
# Note that the file name and the key name are different.
CREDS_NAME = 'wpt-import-export'
KMS_CRYPTO_KEY = (
    'projects/chops-kms/locations/global/keyRings/%s/cryptoKeys/default'
    % CREDS_NAME)


def RunSteps(api):
  api.gclient.set_config('chromium')
  api.bot_update.ensure_checkout()
  api.git('config', 'user.name', 'Chromium WPT Sync',
          name='set git config user.name')
  # LUCI sets user.email automatically.
  api.git_cl.set_config('basic')
  api.git_cl.c.repo_location = api.path['checkout']
  blink_dir = api.path['checkout'].join('third_party', 'blink')
  creds = api.path['cleanup'].join(CREDS_NAME + '.json')
  api.cloudkms.decrypt(
      KMS_CRYPTO_KEY,
      api.repo_resource('recipes', 'recipes', 'assets', CREDS_NAME),
      creds,
  )

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
      creds,
      '--auto-update',
      '--auto-file-bugs',
    ]

    try:
      with api.context(cwd=blink_dir):
        api.python('Import changes from WPT to Chromium', script, args,
                   venv=True)
    finally:
      git_cl_issue_link(api)


def git_cl_issue_link(api):
  """Runs a step which adds a link to the current CL if there is one."""
  issue_step = api.git_cl(
      'issue', ['--json', api.json.output()],
      name='git cl issue'
  )
  issue_result = issue_step.json.output
  if not issue_result or not issue_result.get('issue_url'):
      return
  link_text = 'issue %s' % issue_result['issue']
  issue_step.presentation.links[link_text] = issue_result['issue_url']


def GenTests(api):
  yield (
      api.test('wpt-import-with-issue') +
      api.properties(
          mastername='luci.infra.cron',
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
          mastername='luci.infra.cron',
          buildername='wpt-importer',
          slavename='fake-slave') +
      api.step_data(
          'git cl issue',
          api.json.output({'issue': None, 'issue_url': None})))
