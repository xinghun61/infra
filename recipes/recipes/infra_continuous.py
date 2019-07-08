# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import json

from recipe_engine.recipe_api import Property

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/cipd',
  'depot_tools/depot_tools',
  'depot_tools/gclient',
  'depot_tools/infra_paths',
  'depot_tools/osx_sdk',
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

  'infra_checkout',
  'infra_cipd',
  'infra_system',
]


# Mapping from a builder name to a list of GOOS-GOARCH variants it should build
# CIPD packages for. 'native' means "do not cross-compile, build for the host
# platform". Targeting 'native' will also usually build non-go based packages.
#
# Additionally, a variant may have a sequence of options appended to it,
# separated by colons. e.g. 'VARIANT:option:option'. Currently the supported
# options are:
#   * 'test' - Run the tests. By default no tests are run.
#
# If the builder is not in this set, or the list of GOOS-GOARCH for it is empty,
# it won't be used for building CIPD packages.
#
# Only builders named '*-packager-*' builders will actually upload CIPD
# packages, while '*-continuous-*' builders merely verify that CIPD packages can
# be built.
#
# TODO(iannucci): make packager role explicit with `package=cipd_prefix` option.
# TODO(iannucci): remove this dict and put this all configuration as explicit
#    property inputs to the recipe :)
CIPD_PACKAGE_BUILDERS = {
  # trusty-64 is the primary builder for linux-amd64, and the rest just
  # cross-compile to different platforms (to speed up the overall cycle time by
  # doing stuff in parallel).
  'infra-continuous-precise-64': ['linux-arm', 'linux-arm64'],
  'infra-continuous-trusty-64':  ['native:test', 'linux-386'],
  'infra-continuous-xenial-64':  ['linux-mipsle', 'linux-mips64',
                                  'linux-mips64le'],
  'infra-continuous-yakkety-64': ['linux-s390x'],
  'infra-continuous-zesty-64':   ['linux-ppc64', 'linux-ppc64le'],

  # 10.13 is the primary builder for darwin-amd64.
  'infra-continuous-mac-10.10-64': [],
  'infra-continuous-mac-10.11-64': [],
  'infra-continuous-mac-10.12-64': [],
  'infra-continuous-mac-10.13-64': ['native:test'],

  # Windows 64 bit builder runs and tests for both 64 && 32 bit.
  'infra-continuous-win10-64': ['native:test', 'windows-386:test'],

  # Internal builders, they use exact same recipe.
  'infra-internal-continuous-trusty-64': [
    'native:test',
    'linux-arm',
    'linux-arm64',
  ],
  'infra-internal-continuous-win-64': ['native:test', 'windows-386:test'],
  'infra-internal-continuous-mac-10.10-64': [],
  'infra-internal-continuous-mac-10.11-64': [],
  'infra-internal-continuous-mac-10.13-64': ['native:test'],


  # Builders that upload CIPD packages.
  #
  # In comments is approximate runtime for building and testing packages, per
  # platform (as of Mar 28 2019). We try to balance xc1 and xc2.
  'infra-packager-linux-64': [
    'native:test',       # ~ 140 sec
  ],
  'infra-packager-linux-xc1': [
    'linux-386',         # ~90 sec
    'linux-arm',         # ~90 sec
    'linux-arm64',       # ~90 sec
  ],
  'infra-packager-linux-xc2': [
    'linux-mips64',      # ~50 sec
    'linux-mips64le',    # ~50 sec
    'linux-mipsle',      # ~50 sec
    'linux-ppc64',       # ~40 sec
    'linux-ppc64le',     # ~40 sec
    'linux-s390x',       # ~40 sec
  ],
  'infra-packager-mac-64': ['native:test'],
  'infra-packager-win-64': ['native:test', 'windows-386:test'],

  'infra-internal-packager-linux-64': [
    'native:test',
    'linux-arm',
    'linux-arm64',
  ],
  'infra-internal-packager-mac-64': ['native:test'],
  'infra-internal-packager-win-64': ['native:test', 'windows-386:test'],
}


# A builder responsible for calling "deps.py bundle" to generate cipd bundles
# with vendored go code. We need only one.
GO_DEPS_BUNDLING_BUILDER = 'infra-packager-mac-64'


INTERNAL_REPO = 'https://chrome-internal.googlesource.com/infra/infra_internal'
PUBLIC_REPO = 'https://chromium.googlesource.com/infra/infra'


def RunSteps(api):
  if not api.runtime.is_luci:  # pragma: no cover
    raise ValueError('This recipe is not supported outside of LUCI.')

  buildername = api.buildbucket.builder_name
  if (buildername.startswith('infra-internal-continuous') or
      buildername.startswith('infra-internal-packager')):
    project_name = 'infra_internal'
    repo_url = INTERNAL_REPO
  elif (buildername.startswith('infra-continuous') or
      buildername.startswith('infra-packager')):
    project_name = 'infra'
    repo_url = PUBLIC_REPO
  else:  # pragma: no cover
    raise ValueError(
        'This recipe is not intended for builder %s. ' % buildername)

  co = api.infra_checkout.checkout(
      gclient_config_name=project_name,
      internal=(project_name=='infra_internal'))

  # Prefix the system binary path to PATH so that all Python invocations will
  # use the system Python. This will ensure that packages built will be built
  # aginst the system Python's paths.
  #
  # This is needed by the "infra_python" CIPD package, which incorporates the
  # checkout's VirtualEnv into its packages. This, in turn, results in the CIPD
  # package containing a reference to the Python that was used to create it. In
  # order to control for this, we ensure that the Python is a system Python,
  # which resides at a fixed path.
  with api.infra_system.system_env():
    co.gclient_runhooks()

    # Whatever is checked out by bot_update. It is usually equal to
    # api.buildbucket.gitiles_commit.id except when the build was triggered
    # manually (commit id is empty in that case).
    rev = co.bot_update_step.presentation.properties['got_revision']
    build_main(api, co, buildername, project_name, repo_url, rev)


def build_main(api, checkout, buildername, project_name, repo_url, rev):
  is_packager = 'packager' in buildername

  # Do not run python tests on packager builders, since most of them are
  # irrelevant to the produced packages. Relevant portion of tests will be run
  # from api.infra_cipd.test() below, when testing packages that pack python
  # code.
  if not is_packager:
    run_python_tests(api, project_name)

  # Some third_party go packages on OSX rely on cgo and thus a configured
  # clang toolchain.
  with api.osx_sdk('mac'):
    checkout.ensure_go_env()

    # Call 'deps.py bundle' to package dependencies specified in deps.lock into
    # a CIPD package. This is not strictly necessary, but it significantly
    # reduces time it takes to run 'env.py'. Note that 'deps.py' requires
    # environment produced by 'env.py' (for things like glide and go itself).
    # When the recipe runs with outdated deps bundle, 'env.py' call above falls
    # back to fetching dependencies from git directly. When the bundle is
    # up-to-date, 'deps.py bundle' finishes right away not doing anything.
    if (buildername == GO_DEPS_BUNDLING_BUILDER and
        not api.runtime.is_experimental):
      api.python(
          'bundle go deps',
          api.path['checkout'].join('go', 'env.py'),
          [
            'python',  # env.py knows how to expand 'python' into sys.executable
            api.path['checkout'].join('go', 'deps.py'),
            'bundle',
          ],
          venv=True)

    api.python(
        'infra go tests',
        api.path['checkout'].join('go', 'env.py'),
        ['python', api.path['checkout'].join('go', 'test.py')],
        venv=True)

    for plat in CIPD_PACKAGE_BUILDERS.get(buildername, []):
      options = plat.split(':')
      plat = options.pop(0)

      if plat == 'native':
        goos, goarch = None, None
      else:
        goos, goarch = plat.split('-', 1)

      with api.infra_cipd.context(api.path['checkout'], goos, goarch):
        api.infra_cipd.build()
        if 'test' in options:
          api.infra_cipd.test()
        if is_packager:
          if api.runtime.is_experimental:
            api.step('no CIPD package upload in experimental mode', cmd=None)
          else:
            api.infra_cipd.upload(api.infra_cipd.tags(repo_url, rev))


def run_python_tests(api, project_name):
  with api.step.defer_results():
    with api.context(cwd=api.path['checkout']):
      # Run Linux tests everywhere, Windows tests only on public CI.
      if api.platform.is_linux or project_name == 'infra':
        api.python('infra python tests', 'test.py', ['test'])

      # Validate ccompute configs.
      if api.platform.is_linux and project_name == 'infra_internal':
        api.python(
            'ccompute config test',
            'ccompute/scripts/ccompute_config.py', ['test'])


def GenTests(api):

  def test(name, builder, repo, project, bucket, plat, is_experimental=False):
    return (
        api.test(name) +
        api.platform(plat, 64) +
        api.runtime(is_luci=True, is_experimental=is_experimental) +
        api.buildbucket.ci_build(project, bucket, builder,
                                 git_repo=repo,
                                 build_number=123)
    )

  yield test('public-ci-linux', 'infra-continuous-trusty-64',
             PUBLIC_REPO, 'infra', 'ci', 'linux')
  yield test('public-ci-win', 'infra-continuous-win10-64',
             PUBLIC_REPO, 'infra', 'ci', 'win')

  yield test('internal-ci-linux', 'infra-internal-continuous-trusty-64',
             INTERNAL_REPO, 'infra-internal', 'ci', 'linux')
  yield test('internal-ci-mac', 'infra-internal-continuous-mac-64',
             INTERNAL_REPO, 'infra-internal', 'ci', 'mac')

  yield test('public-packager-mac', 'infra-packager-mac-64',
             PUBLIC_REPO, 'infra-internal', 'prod', 'mac')
  yield test('public-packager-mac_experimental', 'infra-packager-mac-64',
             PUBLIC_REPO, 'infra-internal', 'prod', 'mac',
             is_experimental=True)

  yield test('internal-packager-linux', 'infra-internal-packager-linux-64',
             INTERNAL_REPO, 'infra-internal', 'prod', 'linux')
