# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'bot_update',
  'gclient',
  'git',
  'path',
  'properties',
  'python',
  'raw_io',
  'step',
]


def GenSteps(api):
  project = api.properties['patch_project'] or api.properties['project']
  internal = (project == 'infra_internal')

  api.gclient.set_config(project)
  res = api.bot_update.ensure_checkout(force=True, patch_root=project,
                                       patch_oauth2=internal)
  upstream = res.json.output['properties'].get('got_revision')

  # TODO(sergiyb): This call is copied from run_presubmit.py recipe. We should
  # instead remove this code from here and create a presubmit builder using
  # run_presubmit.py recipe for infra CLs. See http://crbug.com/478651.
  api.git('-c', 'user.email=commit-bot@chromium.org',
          '-c', 'user.name=The Commit Bot',
          'commit', '-a', '-m', 'Committed patch',
          name='commit git patch', cwd=api.path['checkout'])

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

  # TODO(sergiyb): The code below is copied from run_presubmit recipe. We should
  # instead remove this code from here and create a presubmit builder using
  # run_presubmit.py recipe for infra CLs. See http://crbug.com/478651.
  presubmit_args = [
    '--root', api.path['checkout'],
    '--commit',
    '--verbose', '--verbose',
    '--issue', api.properties['issue'],
    '--patchset', api.properties['patchset'],
    '--skip_canned', 'CheckRietveldTryJobExecution',
    '--skip_canned', 'CheckTreeIsOpen',
    '--skip_canned', 'CheckBuildbotPendingBuilds',
    '--rietveld_url', api.properties['rietveld'],
    '--rietveld_fetch',
    '--upstream', upstream,  # '' if not in bot_update mode.
  ]

  if internal:
    presubmit_args.extend([
        '--rietveld_email_file',
        api.path['build'].join('site_config', '.rietveld_client_email')])
    presubmit_args.extend([
        '--rietveld_private_key_file',
        api.path['build'].join('site_config', '.rietveld_secret_key')])
  else:
    presubmit_args.extend(['--rietveld_email', ''])  # activate anonymous mode

  api.python(
      'presubmit', api.path['depot_tools'].join('presubmit_support.py'),
      presubmit_args)


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