# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'bot_update',
  'gclient',
  'git',
  'path',
  'presubmit',
  'properties',
  'python',
  'raw_io',
  'step',
]


def GenSteps(api):
  project = api.properties['patch_project'] or api.properties['project']
  internal = 'internal' in project

  api.gclient.set_config(project)
  api.bot_update.ensure_checkout(force=True, patch_root=project,
                                 patch_oauth2=internal)
  api.gclient.runhooks()

  # Grab a list of changed files.
  result = api.git(
      'diff', '--name-only', 'HEAD', 'HEAD~',
      name='get change list',
      cwd=api.path['checkout'],
      stdout=api.raw_io.output())
  files = result.stdout.splitlines()

  with api.step.defer_results():
    if not all(f.startswith('go/') for f in files):
      api.python('test.py', 'test.py', ['test'], cwd=api.path['checkout'])

    if any(f.startswith('go/') for f in files):
      # Note: env.py knows how to expand 'python' into sys.executable.
      api.python(
          'go test.py', api.path['checkout'].join('go', 'env.py'),
          ['python', api.path['checkout'].join('go', 'test.py')])


def GenTests(api):
  def diff(*files):
    return api.step_data(
        'get change list', api.raw_io.stream_output('\n'.join(files)))

  yield (
    api.test('basic') +
    api.properties.tryserver(
        mastername='tryserver.chromium.linux',
        buildername='infra_tester',
        patch_project='infra') +
    diff('infra/stuff.py', 'go/src/infra/stuff.go')
  )

  yield (
    api.test('only_go') +
    api.properties.tryserver(
        mastername='tryserver.chromium.linux',
        buildername='infra_tester',
        patch_project='infra') +
    diff('go/src/infra/stuff.go')
  )

  yield (
    api.test('only_python') +
    api.properties.tryserver(
        mastername='tryserver.chromium.linux',
        buildername='infra_tester',
        patch_project='infra') +
    diff('infra/stuff.py')
  )

  yield (
    api.test('infra_internal') +
    api.properties.tryserver(
        mastername='internal.infra',
        buildername='infra-internal-tester',
        patch_project='infra_internal') +
    diff('infra/stuff.py', 'go/src/infra/stuff.go')
  )