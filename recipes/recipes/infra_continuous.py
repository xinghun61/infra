# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'bot_update',
  'gclient',
  'git',
  'json',
  'path',
  'properties',
  'python',
  'raw_io',
  'step',
]


def GenSteps(api):
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()

  with api.step.defer_results():
    api.python('infra python tests',
               'test.py', ['test'], cwd=api.path['checkout'])
    # Note: env.py knows how to expand 'python' into sys.executable.
    api.python('infra go tests', api.path['checkout'].join('go', 'env.py'),
               ['python', api.path['checkout'].join('go', 'test.py')])
    api.step('build tests', ['git', 'cl', 'presubmit', '--force'],
             cwd=api.path['slave_build'].join('build'))


def GenTests(api):
  yield (
    api.test('basic') +
    api.properties.tryserver(
        mastername='fake',
        buildername='infra_tester',
        repo_name='infra')
  )
