# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
  'build/file',
  'depot_tools/bot_update',
  'depot_tools/cipd',
  'depot_tools/depot_tools',
  'depot_tools/gclient',
  'depot_tools/infra_paths',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]


# Builder name => [{GOOS: ..., GOARCH: ...}].
CROSS_COMPILING_BUILDERS = {
  'infra-continuous-precise-64': [{'GOOS': 'linux', 'GOARCH': 'arm'},
                                  {'GOOS': 'linux', 'GOARCH': 'arm64'},
                                  {'GOOS': 'linux', 'GOARCH': 'mips64'},
                                  {'GOOS': 'android', 'GOARCH': 'arm'},
                                  {'GOOS': 'android', 'GOARCH': 'amd64'}]
}


# A builder responsible for calling "deps.py bundle" to generate cipd bundles
# with vendored go code. We need only one.
GO_DEPS_BUNDLING_BUILDER = 'infra-continuous-trusty-64'


def build_cipd_packages(api, repo, rev, mastername, buildername, buildnumber,
                        goos, goarch):
  # 'goos' and 'goarch' used for cross-compilation of Go code.
  step_suffix = ''
  env = {}
  if goos or goarch:
    assert goos and goarch, 'Both GOOS and GOARCH should be set'
    step_suffix = ' [GOOS:%s GOARCH:%s]' % (goos, goarch)
    env = {'GOOS': goos, 'GOARCH': goarch}

  # Build packages (don't upload them yet).
  with api.step.context({'env': env}):
    api.python(
        'cipd - build packages' + step_suffix,
        api.path['checkout'].join('build', 'build.py'),
        ['--builder', api.properties.get('buildername')])

  # Verify they are good. Run tests only when building packages for the host
  # platform, since the host can't run binaries build with cross-compilation
  # enabled.
  if not goos and not goarch:
    api.python(
        'cipd - test packages integrity',
        api.path['checkout'].join('build', 'test_packages.py'))

  # Upload them, attach tags.
  tags = [
    'buildbot_build:%s/%s/%s' % (mastername, buildername, buildnumber),
    'git_repository:%s' % repo,
    'git_revision:%s' % rev,
  ]
  try:
    with api.step.context({'env': env}):
      return api.python(
          'cipd - upload packages' + step_suffix,
          api.path['checkout'].join('build', 'build.py'),
          [
            '--no-rebuild',
            '--upload',
            '--service-account-json',
            api.cipd.default_bot_service_account_credentials,
            '--json-output', api.json.output(),
            '--builder', api.properties.get('buildername'),
          ] + ['--tags'] + tags)
  finally:
    step_result = api.step.active_result
    output = step_result.json.output or {}
    p = step_result.presentation
    for pkg in output.get('succeeded', []):
      info = pkg['info']
      title = '%s %s' % (info['package'], info['instance_id'])
      p.links[title] = info.get('url', 'http://example.com/not-implemented-yet')


def build_luci(api):
  go_bin = api.path['checkout'].join('go', 'bin')
  go_env = api.path['checkout'].join('go', 'env.py')
  api.file.rmcontents('clean go bin', go_bin)

  api.python(
      'build luci-go', go_env,
      ['go', 'install', 'github.com/luci/luci-go/client/cmd/...'])

  files = sorted(api.file.listdir('listing go bin', go_bin))
  absfiles = [api.path.join(go_bin, i) for i in files]
  with api.step.context({'env': {
      'DEPOT_TOOLS_GSUTIL_BIN_DIR': api.path['cache'].join('gsutil')}}):
    api.python(
        'upload go bin',
        api.depot_tools.upload_to_google_storage_path,
        ['-b', 'chromium-luci'] + absfiles)
  for name, abspath in zip(files, absfiles):
    sha1 = api.file.read(
        '%s sha1' % str(name), abspath + '.sha1',
        test_data='0123456789abcdeffedcba987654321012345678')
    api.step.active_result.presentation.step_text = sha1


PROPERTIES = {
  'mastername': Property(),
  'buildername': Property(),
  'buildnumber': Property(default=-1, kind=int),
}

def RunSteps(api, mastername, buildername, buildnumber):
  if buildername.startswith('infra-internal-continuous'):
    project_name = 'infra_internal'
    repo_name = 'https://chrome-internal.googlesource.com/infra/infra_internal'
  elif buildername.startswith('infra-continuous'):
    project_name = 'infra'
    repo_name = 'https://chromium.googlesource.com/infra/infra'
  else:  # pragma: no cover
    raise ValueError(
        'This recipe is not intended for builder %s. ' % buildername)

  api.gclient.set_config(project_name)
  bot_update_step = api.bot_update.ensure_checkout()
  api.gclient.runhooks()

  # Whatever is checked out by bot_update. It is usually equal to
  # api.properties['revision'] except when the build was triggered manually
  # ('revision' property is missing in that case).
  rev = bot_update_step.presentation.properties['got_revision']

  with api.step.defer_results():
    with api.step.context({'cwd': api.path['checkout']}):
      # Run Linux tests everywhere, Windows tests only on public CI.
      if api.platform.is_linux or project_name == 'infra':
        api.python(
            'infra python tests',
            'test.py',
            ['test', '--jobs', 1])

      # Run Glyco tests only on public Linux\Mac CI.
      if project_name == 'infra' and not api.platform.is_win:
        api.python(
            'Glyco tests',
            api.path['checkout'].join('glyco', 'tests', 'run_all_tests.py'),
            venv=True)

    # This downloads Go third parties, so that the next step doesn't have junk
    # output in it.
    api.python(
        'go third parties',
        api.path['checkout'].join('go', 'env.py'),
        ['go', 'version'])

    # Call 'deps.py bundle' to package dependencies specified in deps.lock into
    # a CIPD package. This is not strictly necessary, but it significantly
    # reduces time it takes to run 'env.py'. Note that 'deps.py' requires
    # environment produced by 'env.py' (for things like glide and go itself).
    # When the recipe runs with outdated deps bundle, 'env.py' call above falls
    # back to fetching dependencies from git directly. When the bundle is
    # up-to-date, 'deps.py bundle' finishes right away not doing anything.
    if buildername == GO_DEPS_BUNDLING_BUILDER:
      api.python(
          'bundle go deps',
          api.path['checkout'].join('go', 'env.py'),
          [
            'python',  # env.py knows how to expand 'python' into sys.executable
            api.path['checkout'].join('go', 'deps.py'),
            'bundle',
            '--service-account-json',
            api.cipd.default_bot_service_account_credentials,
          ])

    api.python(
        'infra go tests',
        api.path['checkout'].join('go', 'env.py'),
        ['python', api.path['checkout'].join('go', 'test.py')])

  if buildnumber != -1:
    build_cipd_packages(api, repo_name, rev, mastername, buildername,
                        buildnumber, None, None)
    for spec in CROSS_COMPILING_BUILDERS.get(buildername, []):
      build_cipd_packages(api, repo_name, rev, mastername, buildername,
                          buildnumber, spec['GOOS'], spec['GOARCH'])
  else:
    result = api.step('cipd - not building packages', None)
    result.presentation.status = api.step.WARNING

  # Only build luci-go executables on 64 bits, public CI.
  if project_name == 'infra' and buildername.endswith('-64'):
    build_luci(api)


def GenTests(api):
  cipd_json_output = {
    'succeeded': [
      {
        'info': {
          'instance_id': 'abcdefabcdef63ad814cd1dfffe2fcfc9f81299c',
          'package': 'infra/tools/some_tool/linux-bitness',
        },
        'pkg_def_name': 'some_tool',
      },
    ],
    'failed': [],
  }

  yield (
    api.test('infra') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-continuous',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/infra',
    ) +
    api.override_step_data(
        'cipd - upload packages', api.json.output(cipd_json_output))
  )
  yield (
    api.test('infra_win') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-continuous',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/infra',
    ) +
    api.platform.name('win')
  )
  yield (
    api.test('infra_internal') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-internal-continuous',
        buildnumber=123,
        mastername='internal.infra',
        repository=
            'https://chrome-internal.googlesource.com/infra/infra_internal',
    ) +
    api.override_step_data(
        'cipd - upload packages', api.json.output(cipd_json_output))
  )
  yield (
    api.test('infra-64') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-continuous-64',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/infra',
    )
  )

  yield (
    api.test('infra-cross-compile') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-continuous-precise-64',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/infra',
    ) +
    api.override_step_data(
        'cipd - upload packages', api.json.output(cipd_json_output)) +
    api.override_step_data(
        'cipd - upload packages [GOOS:linux GOARCH:arm]',
        api.json.output(cipd_json_output)) +
    api.override_step_data(
        'cipd - upload packages [GOOS:android GOARCH:arm]',
        api.json.output(cipd_json_output))
  )

  yield (
    api.test('infra-go-deps-bundle') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-continuous-trusty-64',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/infra',
    )
  )

  yield (
    api.test('infra_swarming') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-continuous-32',
        buildnumber=-1,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/infra',
    )
  )
