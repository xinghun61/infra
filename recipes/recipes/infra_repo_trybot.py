# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'bot_update',
  'gclient',
  'path',
  'python',
  'properties',
]

def GenSteps(api):
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout(force=True, patch_root='infra')
  api.gclient.runhooks()
  api.python('test.py', api.path['checkout'].join('test.py'))


def GenTests(api):
  yield api.test('basic') + api.properties(
    mastername='fake master',
    buildername='fake builder',
    slavename='fake slave',
  )
