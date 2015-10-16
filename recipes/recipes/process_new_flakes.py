# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs a pipeline to create/update issues for flaky tests/steps."""


DEPS = [
  'bot_update',
  'gclient',
  'path',
  'properties',
  'python',
]


def RunSteps(api):
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()

  cmd = ['infra.tools.process_new_flakes',
         '--crbug-service-account',
         '/creds/service_accounts/service-account-chromium-try-flakes.json']
  api.python('process new flakes', 'run.py', cmd,
             cwd=api.path['slave_build'].join('infra'))


def GenTests(api):
  yield (api.test('basic') +
         api.properties(mastername='chromium.infra.cron',
                        buildername='process-new-flakes',
                        slavename='fake-slave'))
