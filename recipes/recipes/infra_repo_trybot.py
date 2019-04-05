# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/osx_sdk',
  'infra_checkout',
  'infra_system',
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/runtime',
  'recipe_engine/step',
]


def RunSteps(api):
  cl = api.buildbucket.build.input.gerrit_changes[0]
  project = cl.project
  assert project in ('infra/infra', 'infra/infra_internal'), (
      'unknown project: "%s"' % project)
  patch_root = project.split('/')[-1]
  internal = (patch_root == 'infra_internal')
  co = api.infra_checkout.checkout(
      gclient_config_name=patch_root, patch_root=patch_root, internal=internal)
  co.commit_change()
  co.gclient_runhooks()

  files = co.get_changed_files()
  is_deps_roll = 'DEPS' in files

  with api.step.defer_results():
    with api.context(cwd=co.path.join(patch_root)):
      api.python('python tests', 'test.py', ['test'])
      # To preserve high CQ coverage vs very low coverage in infra_internal,
      # test CQ separately. But only if CQ code is modified.
      # Note that this will run CQ tests once again.
      if internal and any(f.startswith('infra_internal/services/cq')
                          for f in files):
        api.python('python cq tests', 'test.py',
                   ['test', 'infra_internal/services/cq'])

    if not internal:
      # TODO(phajdan.jr): should we make recipe tests run on other platforms?
      # TODO(tandrii): yes, they should run on Mac as well.
      if api.platform.is_linux and api.platform.bits == 64:
        api.python(
            'recipe test',
            co.path.join('infra', 'recipes', 'recipes.py'),
            ['test', 'run'])
        api.python(
            'recipe lint',
            co.path.join('infra', 'recipes', 'recipes.py'),
            ['lint'])

    if api.platform.is_linux and (is_deps_roll or
        any(f.startswith('appengine/chromium_rietveld') for f in files)):
      with api.context(cwd=co.path.join('infra')):
        api.step('rietveld tests',
                 ['make', '-C', 'appengine/chromium_rietveld', 'test'])

  # Some third_party go packages on OSX rely on cgo and thus a configured
  # clang toolchain.
  with api.osx_sdk('mac'):
    # Ensure go is bootstrapped as a separate step.
    co.ensure_go_env()

    # Note: go/env.py knows how to expand 'python' into sys.executable (perhaps
    # 'vpython').
    co.go_env_step(
        'python', str(co.path.join(patch_root, 'go', 'test.py')),
        name='go tests')

    # Do slow *.cipd packaging tests only when touching build/* or DEPS. This
    # will build all registered packages (without uploading them), and run
    # package tests from build/tests/.
    #
    # When we run these tests, prefix the system binary path to PATH so that
    # all Python invocations will use the system Python. This will ensure that
    # packages are built and tested against the version of Python that they
    # will run on,
    if any(f.startswith('build/') for f in files) or is_deps_roll:
      with api.infra_system.system_env():
        api.python(
            'cipd - build packages',
            co.path.join(patch_root, 'build', 'build.py'),
            venv=True)
        api.python(
            'cipd - test packages integrity',
            co.path.join(patch_root, 'build', 'test_packages.py'),
            venv=True)
    else:
      api.step('skipping slow cipd packaging tests', cmd=None)


def GenTests(api):
  def diff(*files):
    return api.step_data(
        'get change list', api.raw_io.stream_output('\n'.join(files)))

  def test(name, internal=False, buildername='generic tester'):
    return (
      api.test(name)
      + api.runtime(is_luci=True, is_experimental=True)
      + api.buildbucket.try_build(
        project='infra-internal' if internal else 'infra',
        builder=buildername,
        git_repo=(
          'https://chrome-internal.googlesource.com/infra/infra_internal'
          if internal else
          'https://chromium.googlesorce.com/infra/infra'
        )
      )
    )

  yield (
    test('basic') +
    diff('infra/stuff.py', 'go/src/infra/stuff.go')
  )

  yield (
    test('basic_internal', internal=True) +
    diff('infra/stuff.py', 'go/src/infra/stuff.go')
  )

  yield (
    test('only_go') +
    diff('go/src/infra/stuff.go')
  )

  yield (
    test('only_go_osx') +
    api.platform('mac', 64) +
    diff('go/src/infra/stuff.go')
  )

  yield (
    test('only_js') +
    diff('appengine/foo/static/stuff.js')
  )

  yield (
    test('infra_internal_with_cq', internal=True) +
    diff('infra_internal/services/cq/cq.py')
  )

  yield (
    test('rietveld_tests') +
    diff('appengine/chromium_rietveld/codereview/views.py')
  )

  yield (
    test('only_cipd_build') +
    diff('build/build.py')
  )
