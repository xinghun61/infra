# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'gclient',
  'path',
  'properties',
  'python',
]

def GenSteps(api):
  api.gclient.set_config('infra')
  api.gclient.checkout()
  api.gclient.runhooks()
  api.python('test.py', api.path['checkout'].join('test.py'))

  # FIXME: This is copied from the run_presubmit.py recipe.
  # We should instead share code!
  api.python('presubmit',
    api.path['depot_tools'].join('presubmit_support.py'),
    ['--commit',
    '--verbose', '--verbose',
    '--issue', api.properties['issue'],
    '--patchset', api.properties['patchset'],
    '--skip_canned', 'CheckRietveldTryJobExecution',
    '--skip_canned', 'CheckTreeIsOpen',
    '--skip_canned', 'CheckBuildbotPendingBuilds',
    '--rietveld_url', api.properties['rietveld'],
    '--rietveld_email', '',  # activates anonymous mode
    '--rietveld_fetch'])


def GenTests(api):
  yield api.test('basic') + api.properties.tryserver()

