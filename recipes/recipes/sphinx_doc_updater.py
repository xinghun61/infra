# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Compile and deploy infra.git documentation."""

DEPS = [
  'bot_update',
  'gclient',
  'gsutil',
  'path',
  'properties',
  'python',
]


def RunSteps(api):
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()

  # Update documentation
  api.python('Clean documentation',
             api.path['slave_build'].join('infra', 'run.py'),
             ['infra.tools.docgen', 'clean'])
  api.python('Generate documentation',
             api.path['slave_build'].join('infra', 'run.py'),
             ['infra.tools.docgen'])

  # Upload generated documentation
  api.gsutil.upload(
    api.path['slave_build'].join('infra', 'doc', 'html'),
    'chromium-infra-docs', 'infra',
    args=['-R'],
    link_name='Deploy documentation to GCS',
    use_retry_wrapper=False)


def GenTests(api):
  yield (
      api.test('basic') +
      api.properties(mastername='fake', buildername='fake',
                     slavename='fake')
  )
