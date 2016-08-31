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
    force=True, patch_root=project, patch_oauth2=internal,
    use_site_config_creds=False)

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
  result.presentation.logs['change list'] = files

  with api.step.defer_results():
    # Rietveld tests.
    deps_mod = 'DEPS' in files

    api.python('python tests', 'test.py', ['test', '--jobs', 1],
               cwd=api.path['checkout'])

    if not internal:
      # TODO(phajdan.jr): should we make recipe tests run on other platforms?
      if api.platform.is_linux and api.platform.bits == 64:
        api.python(
            'recipe tests', api.path['checkout'].join('recipes', 'recipes.py'),
            ['simulation_test', 'test'])

      api.python(
          'recipe lint', api.path['checkout'].join('recipes', 'recipes.py'),
          ['lint'])

    # if any(f.startswith('infra/glyco/') for f in files):
    #   api.python(
    #     'glyco tests',
    #     api.path['checkout'].join('glyco', 'tests', 'run_all_tests.py'),
    #     [], cwd=api.path['checkout'])

    # Ensure go is bootstrapped as a separate step.
    api.python('go bootstrap', api.path['checkout'].join('go', 'env.py'))

    # Note: env.py knows how to expand 'python' into sys.executable.
    api.python(
        'go tests', api.path['checkout'].join('go', 'env.py'),
        ['python', api.path['checkout'].join('go', 'test.py')])

    if api.platform.is_linux and (deps_mod or
        any(f.startswith('appengine/chromium_rietveld') for f in files)):
      api.step('rietveld tests',
               ['make', '-C', 'appengine/chromium_rietveld', 'test'],
               cwd=api.path['checkout'])


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
    api.properties.tryserver_gerrit(
        full_project_name='infra/infra',
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
    api.test('only_glyco_python') +
    api.properties.tryserver(
        mastername='tryserver.chromium.linux',
        buildername='infra_tester',
        patch_project='infra') +
    diff('infra/glyco/stuff.py')
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
    api.properties.tryserver_gerrit(
        full_project_name='infra/infra_internal',
        gerrit_host='chrome-internal-review.googlesource.com',
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
