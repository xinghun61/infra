# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs a pipeline to detect suspicious commits in Chromium."""


DEPS = [
  'bot_update',
  'gclient',
  'gsutil',
  'path',
  'properties',
  'python',
]


def RunSteps(api):
  api.gclient.set_config('infra_with_chromium')
  api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()
  filename = api.path.mkdtemp('antibody')

  cmd = ['infra.tools.antibody']
  cmd.extend(['--sql-password-file', '/home/chrome-bot/.antibody_password'])
  cmd.extend(['--git-checkout-path', api.m.path['root'].join('src')])
  cmd.extend(['--html-output-file', filename])
  cmd.extend(['--since', '2015.01.01'])
  cmd.extend(['--run-antibody'])

  api.python('Antibody', 'run.py', cmd)
  api.gsutil(['cp', filename, 'gs://chromium-antibody/report.html'])


def GenTests(api):
  yield (api.test('antibody') +
         api.properties(mastername='chromium.infra.cron',
                        buildername='antibody',
                        slavename='fake-slave'))
