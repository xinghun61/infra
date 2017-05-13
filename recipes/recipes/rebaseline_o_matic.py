# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Generates new baselines for Blink layout tests that need rebaselining.

Intended to be called periodically. Syncs to the Blink repo and runs
'webkit-patch auto-rebaseline', which processes entries in
LayoutTests/TestExpectations that are marked with 'NeedsRebaseline'.

Slaves running this recipe will require SVN access credentials for submitting
patches with the new baselines.
"""

DEPS = [
  'build/chromium',
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'recipe_engine/context',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]


def RunSteps(api):
  RIETVELD_REFRESH_TOKEN = '/creds/refresh_tokens/blink_rebaseline_bot_rietveld'

  api.gclient.set_config('chromium')
  api.bot_update.ensure_checkout()

  cwd = api.path['checkout'].join('third_party', 'WebKit')

  # Changes should be committed and landed as the rebaseline bot role account.
  # The base chromium repo setup configures chrome-bot@ as the author/committer.
  # We could attempt use of command-line arguments to git commands to specify
  # the rebaseline bot name/email, but in fact this is insufficient to override
  # due to precedence. Environment variables would likely work per the man page
  # for git-commit-tree, but would require changes through both the auto-
  # rebaseline script and 'git cl land', with this bot as the only intended
  # customer.
  #
  # Given all tradeoffs, setting the chromium repo's user name/email to the
  # intended rebaseline bot parameters in a persistent manner is deemed a
  # reasonable alternate approach.
  api.git('config', 'user.name', 'Rebaseline Bot')
  api.git('config', 'user.email', 'blink-rebaseline-bot@chromium.org')

  with api.context(cwd=cwd):
    api.python('webkit-patch auto-rebaseline',
               cwd.join('Tools', 'Scripts', 'webkit-patch'),
               ['auto-rebaseline', '--verbose',
               '--auth-refresh-token-json', RIETVELD_REFRESH_TOKEN])


def GenTests(api):
  yield (api.test('rebaseline_o_matic') +
         api.properties(mastername='chromium.infra.cron',
                        buildername='rebaseline-o-matic',
                        slavename='fake-slave'))

