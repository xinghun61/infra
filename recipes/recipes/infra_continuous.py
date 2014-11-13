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
]


def GenSteps(api):
  # FIXME: Much of this code (bot_update, get upstream and commit patch so
  # presubmit_support doesn't freak out, run presubmit) is copied directly from
  # the run_presubmit.py recipe. We should instead share code!
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()

  api.python('test.py', 'test.py', cwd=api.path['checkout'])

  # Note: env.py knows how to expand 'python' into sys.executable.
  api.python(
    'go test.py', api.path['checkout'].join('go', 'env.py'),
    ['python', api.path['checkout'].join('go', 'test.py')])


def GenTests(api):
  yield (
    api.test('basic') +
    api.properties.tryserver(
        mastername='fake',
        buildername='infra_tester',
        repo_name='infra')
  )
