# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
]


def RunSteps(api):
  project = api.properties['patch_project'] or api.properties['project']
  # In case of Gerrit tryjob, project is infra/infra or infra/infra_internal.
  if project in ('infra/infra', 'infra/infra_internal'):
    project = project.split('/')[-1]
  assert project in ('infra', 'infra_internal'), (
      'unknown project: "%s"' % project)
  internal = (project == 'infra_internal')
  api.gclient.set_config(project)
  api.bot_update.ensure_checkout(
    patch_root=project, patch_oauth2=internal, use_site_config_creds=False)

  with api.step.context({'cwd': api.path['checkout']}):
    api.git('-c', 'user.email=commit-bot@chromium.org',
            '-c', 'user.name=The Commit Bot',
            'commit', '-a', '-m', 'Committed patch',
            name='commit git patch')

  api.gclient.runhooks()

  # Grab a list of changed files.
  with api.step.context({'cwd': api.path['checkout']}):
    result = api.git(
        'diff', '--name-only', 'HEAD', 'HEAD~',
        name='get change list',
        stdout=api.raw_io.output())
  files = result.stdout.splitlines()
  result.presentation.logs['change list'] = files

  is_deps_roll = 'DEPS' in files

  with api.step.defer_results():
    with api.step.context({'cwd': api.path['checkout']}):
      api.python('python tests', 'test.py', ['test', '--jobs', 1])

    if not internal:
      # TODO(phajdan.jr): should we make recipe tests run on other platforms?
      if api.platform.is_linux and api.platform.bits == 64:
        # Run both current simulation test logic (simulation_test),
        # and experimental (test). Eventually the former will be removed.
        api.python(
            'recipe test',
            api.path['checkout'].join('recipes', 'recipes.py'),
            ['--use-bootstrap', 'test', 'run'])
        api.python(
            'recipe simulation_tests',
            api.path['checkout'].join('recipes', 'recipes.py'),
            ['simulation_test', 'test'])
        api.python(
            'recipe lint', api.path['checkout'].join('recipes', 'recipes.py'),
            ['lint'])

    # Ensure go is bootstrapped as a separate step.
    api.python('go bootstrap', api.path['checkout'].join('go', 'env.py'))

    # Note: env.py knows how to expand 'python' into sys.executable.
    api.python(
        'go tests', api.path['checkout'].join('go', 'env.py'),
        ['python', api.path['checkout'].join('go', 'test.py')])

    # Do slow *.cipd packaging tests only when touching build/* or DEPS. This
    # will build all registered packages (without uploading them), and run
    # package tests from build/tests/.
    if any(f.startswith('build/') for f in files) or is_deps_roll:
      api.python(
          'cipd - build packages',
          api.path['checkout'].join('build', 'build.py'))
      api.python(
          'cipd - test packages integrity',
          api.path['checkout'].join('build', 'test_packages.py'))

    if api.platform.is_linux and (is_deps_roll or
        any(f.startswith('appengine/chromium_rietveld') for f in files)):
      with api.step.context({'cwd': api.path['checkout']}):
        api.step('rietveld tests',
                 ['make', '-C', 'appengine/chromium_rietveld', 'test'])


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
    api.test('basic_gerrit') +
    api.properties.tryserver(
        gerrit_project='infra/infra',
        mastername='tryserver.infra',
        buildername='infra_tester') +
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
    api.test('only_js') +
    api.properties.tryserver(
        mastername='tryserver.chromium.linux',
        buildername='infra_tester',
        patch_project='infra') +
    diff('appengine/foo/static/stuff.js')
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

  yield (
    api.test('infra_internal_gerrit') +
    api.properties.tryserver(
        gerrit_project='infra/infra_internal',
        gerrit_url='https://chrome-internal-review.googlesource.com',
        mastername='tryserver.infra',
        buildername='infra_tester') +
    diff('infra/stuff.py', 'go/src/infra/stuff.go')
  )

  yield (
    api.test('rietveld_tests') +
    api.properties.tryserver(
        mastername='tryserver.chromium.linux',
        buildername='infra_tester',
        patch_project='infra') +
    diff('appengine/chromium_rietveld/codereview/views.py')
  )

  yield (
    api.test('rietveld_tests_on_win') +
    api.properties.tryserver(
        mastername='tryserver.chromium.linux',
        buildername='infra_tester',
        patch_project='infra') +
    diff('appengine/chromium_rietveld/codereview/views.py') +
    api.platform.name('win')
  )

  yield (
    api.test('only_DEPS') +
    api.properties.tryserver(
        mastername='tryserver.chromium.linux',
        buildername='infra_tester',
        patch_project='infra') +
    diff('DEPS')
  )

  yield (
    api.test('only_cipd_build') +
    api.properties.tryserver(
        mastername='tryserver.chromium.linux',
        buildername='infra_tester',
        patch_project='infra') +
    diff('build/build.py')
  )
