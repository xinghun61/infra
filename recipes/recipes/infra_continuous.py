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
  builder_name = api.properties.get('buildername')
  if builder_name == 'infra-internal-continuous':
    project_name = 'infra_internal'
  elif builder_name == 'infra-continuous':
    project_name = 'infra'
  else:  #pragma: no cover
    raise ValueError('This recipe is not intended for builder %s. '
                     % builder_name)

  api.gclient.set_config(project_name)
  api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()

  with api.step.defer_results():
    api.python('infra python tests',
               'test.py', ['test'], cwd=api.path['checkout'])
    # Note: env.py knows how to expand 'python' into sys.executable.
    api.python('infra go tests', api.path['checkout'].join('go', 'env.py'),
               ['python', api.path['checkout'].join('go', 'test.py')])


def GenTests(api):
  yield (
    api.test('infra') +
    api.properties.tryserver(
        buildername='infra-continuous')
  )
  yield (
    api.test('infra_internal') +
    api.properties.tryserver(
        buildername='infra-internal-continuous')

  )
