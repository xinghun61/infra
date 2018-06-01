# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from recipe_engine.recipe_api import Property

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/cipd',
  'depot_tools/depot_tools',
  'depot_tools/gclient',
  'depot_tools/infra_paths',
  'infra_system',
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/runtime',
  'recipe_engine/step',
]


# Mapping from a builder name to a list of GOOS-GOARCH variants it should build
# CIPD packages for. 'native' means "do not cross-compile, build for the host
# platform". Targeting 'native' will also usually build non-go based packages.
#
# If the builder is not in this set, or the list of GOOS-GOARCH for it is empty,
# it won't be used for building CIPD packages.
CIPD_PACKAGE_BUILDERS = {
  # trusty-32 is the primary builder for linux-386.
  'infra-continuous-precise-32': [],
  'infra-continuous-trusty-32':  ['native'],

  # trusty-64 is the primary builder for linux-amd64, and the rest just
  # cross-compile to different platforms (to speed up the overall cycle time by
  # doing stuff in parallel).
  'infra-continuous-precise-64': ['linux-arm', 'linux-arm64'],
  'infra-continuous-trusty-64':  ['native'],
  'infra-continuous-xenial-64':  ['linux-mips64'],
  'infra-continuous-yakkety-64': ['linux-s390x'],
  'infra-continuous-zesty-64':   ['linux-ppc64', 'linux-ppc64le'],

  # 10.13 is the primary builder for darwin-amd64.
  'infra-continuous-mac-10.10-64': [],
  'infra-continuous-mac-10.11-64': [],
  'infra-continuous-mac-10.12-64': [],
  'infra-continuous-mac-10.13-64': ['native'],

  # Windows builders each build and test for their own bitness.
  'infra-continuous-win-32': ['native'],
  'infra-continuous-win-64': ['native'],

  # Internal builders, they use exact same recipe.
  'infra-internal-continuous-trusty-64': ['native', 'linux-arm', 'linux-arm64'],
  'infra-internal-continuous-trusty-32': ['native'],
  'infra-internal-continuous-win-32': ['native'],
  'infra-internal-continuous-win-64': ['native'],
  'infra-internal-continuous-mac-10.10-64': [],
  'infra-internal-continuous-mac-10.11-64': [],
  'infra-internal-continuous-mac-10.13-64': ['native'],
}


# Set of builders that build and upload LUCI binaries to Google Storage, for
# clients that don't use CIPD (like chromium/src hooks).
LEGACY_LUCI_BUILDERS = {
  'infra-continuous-trusty-64',
  'infra-continuous-mac-10.13-64',
  'infra-continuous-win-64',
}


# A builder responsible for calling "deps.py bundle" to generate cipd bundles
# with vendored go code. We need only one.
GO_DEPS_BUNDLING_BUILDER = 'infra-continuous-trusty-64'


def get_go_platforms_for_cipd(builder):
  """Yields a list of (GOOS, GOARCH) to build for on the given builder."""
  for plat in CIPD_PACKAGE_BUILDERS.get(builder, []):
    if plat == 'native':
      yield None, None  # reset GOOS and GOARCH
    else:
      yield plat.split('-', 1)


def build_cipd_packages(
    api, repo, rev, bucket, buildername, buildnumber, goos, goarch):
  # 'goos' and 'goarch' are used for cross-compilation of Go code.
  step_suffix = ''
  env = {}
  if goos or goarch:
    assert goos and goarch, 'Both GOOS and GOARCH should be set'
    step_suffix = ' [GOOS:%s GOARCH:%s]' % (goos, goarch)
    env = {'GOOS': goos, 'GOARCH': goarch}

  # Build packages (don't upload them yet).
  with api.context(env=env):
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
  if api.runtime.is_luci:
    build_tag_key = 'luci_build'
  else:
    # TODO(tandrii): get rid of this once migrated to LUCI.
    build_tag_key = 'buildbot_build'
  tags = [
    '%s:%s/%s/%s' % (build_tag_key, bucket, buildername, buildnumber),
    'git_repository:%s' % repo,
    'git_revision:%s' % rev,
  ]
  try:
    with api.context(env=env):
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
      ['go', 'install', 'go.chromium.org/luci/client/cmd/...'])

  absfiles = api.file.listdir('listing go bin', go_bin,
                              test_data=['file 1', 'file 2'])
  with api.context(env={
      'DEPOT_TOOLS_GSUTIL_BIN_DIR': api.path['cache'].join('gsutil')}):
    api.python(
        'upload go bin',
        api.depot_tools.upload_to_google_storage_path,
        ['-b', 'chromium-luci'] + absfiles)
  for abspath in absfiles:
    sha1 = api.file.read_text(
        '%s sha1' % str(abspath.pieces[-1]), str(abspath) + '.sha1',
        test_data='0123456789abcdeffedcba987654321012345678')
    api.step.active_result.presentation.step_text = sha1


PROPERTIES = {
  # TODO(tandrii): get rid of mastername once migrated to LUCI.
  'mastername': Property(default=None),
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

  if api.runtime.is_luci:
    bucket = api.buildbucket.properties['build']['bucket']
  else:
    bucket = mastername

  # Prefix the system binary path to PATH so that all Python invocations will
  # use the system Python. This will ensure that packages built will be built
  # aginst the system Python's paths.
  #
  # This is needed by the "infra_python" CIPD package, which incorporates the
  # checkout's VirtualEnv into its packages. This, in turn, results in the CIPD
  # package containing a reference to the Python that was used to create it. In
  # order to control for this, we ensure that the Python is a system Python,
  # which resides at a fixed path.
  api.gclient.set_config(project_name)
  with api.infra_system.system_env():
    bot_update_step = api.bot_update.ensure_checkout()
    api.gclient.runhooks()

    # Whatever is checked out by bot_update. It is usually equal to
    # api.properties['revision'] except when the build was triggered manually
    # ('revision' property is missing in that case).
    rev = bot_update_step.presentation.properties['got_revision']

    build_main(api, bucket, buildername, buildnumber, project_name,
               repo_name, rev)


def build_main(api, bucket, buildername, buildnumber, project_name,
               repo_name, rev):

  with api.step.defer_results():
    with api.context(cwd=api.path['checkout']):
      # Run Linux tests everywhere, Windows tests only on public CI.
      if api.platform.is_linux or project_name == 'infra':
        # TODO(tandrii): maybe get back coverage on 32-bit once
        # http://crbug/766416 is resolved.
        args = ['test']
        if (api.platform.is_linux and api.platform.bits == 32 and
            project_name == 'infra_internal'):  # pragma: no cover
          args.append('--no-coverage')
        api.python('infra python tests', 'test.py', args)

      # Validate ccompute configs.
      if api.platform.is_linux and project_name == 'infra_internal':
        api.python(
            'ccompute config test',
            'ccompute/scripts/ccompute_config.py', ['test'])

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
    for goos, goarch in get_go_platforms_for_cipd(buildername):
      build_cipd_packages(
          api, repo_name, rev, bucket, buildername, buildnumber,
          goos, goarch)
  else:  # pragma: no cover
    result = api.step('cipd - not building packages, no buildnumber', None)
    result.presentation.status = api.step.WARNING

  if buildername in LEGACY_LUCI_BUILDERS:
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
    api.test('infra-continuous-precise-64') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-continuous-precise-64',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/infra',
    ) +
    api.override_step_data(
        'cipd - upload packages [GOOS:linux GOARCH:arm]',
        api.json.output(cipd_json_output)) +
    api.override_step_data(
        'cipd - upload packages [GOOS:linux GOARCH:arm64]',
        api.json.output(cipd_json_output))
  )
  yield (
    api.test('infra-continuous-trusty-64') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-continuous-trusty-64',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/infra',
    ) +
    api.override_step_data(
        'cipd - upload packages', api.json.output(cipd_json_output))
  )
  yield (
    api.test('infra-continuous-win-64') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-continuous-win-64',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/infra',
    ) +
    api.platform.name('win')
  )
  yield (
    api.test('infra-internal-continuous') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-internal-continuous-trusty-32',
        buildnumber=123,
        mastername='internal.infra',
        repository=
            'https://chrome-internal.googlesource.com/infra/infra_internal',
    ) +
    api.override_step_data(
        'cipd - upload packages', api.json.output(cipd_json_output))
  )
  yield (
    api.test('infra-internal-continuous-luci') +
    api.runtime(is_luci=True, is_experimental=True) +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='infra-internal-continuous-trusty-32',
        buildnumber=123,
        repository=
            'https://chrome-internal.googlesource.com/infra/infra_internal',
        buildbucket=json.dumps({
          "build": {
            "bucket": "luci.infra-internal.ci",
            "created_by": "user:luci-scheduler@appspot.gserviceaccount.com",
            "created_ts": 1527292217677440,
            "id": "8945511751514863184",
            "project": "infra-internal",
            "tags": [
              "builder:infra-internal-continuous-trusty-32",
              ("buildset:commit/gitiles/chrome-internal.googlesource.com/" +
                "infra/infra_internal/" +
                "+/2d72510e447ab60a9728aeea2362d8be2cbd7789"),
              "gitiles_ref:refs/heads/master",
              "scheduler_invocation_id:9110941813804031728",
              "user_agent:luci-scheduler",
            ],
          },
          "hostname": "cr-buildbucket.appspot.com"
        }),
    ) +
    api.override_step_data(
        'cipd - upload packages', api.json.output(cipd_json_output))
  )
