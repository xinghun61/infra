# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This recipe builds and packages third party software, such as Git."""

from recipe_engine.recipe_api import Property


DEPS = [
  'depot_tools/cipd',
  'depot_tools/gitiles',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/runtime',
  'recipe_engine/step',
  'third_party_packages',
]

PROPERTIES = {
  'cross_platform': Property(
      kind=str, default=None,
      help=('Target cross-compile platform. Must be in '
            '("linux-arm64", "linux-armv6l", "linux-mips32", "linux-mips64"). '
            'Requires working docker implementation on $PATH.')),
}

def RunSteps(api, cross_platform):
  api.third_party_packages.init_cross_platform(cross_platform)
  api.third_party_packages.dry_run = api.runtime.is_experimental
  if not api.runtime.is_experimental and not api.runtime.is_luci:
    # TODO(Tandrii): delete with buildbot.
    api.cipd.set_service_account_credentials(
        api.cipd.default_bot_service_account_credentials)

  with api.step.defer_results():
    with api.step.nest('python'):
      api.third_party_packages.python.package()
    with api.step.nest('git'):
      api.third_party_packages.git.package()
    with api.step.nest('gcloud'):
      api.third_party_packages.gcloud.package()
    with api.step.nest('gsutil'):
      api.third_party_packages.gsutil.package()
    with api.step.nest('ninja'):
      api.third_party_packages.ninja.package()
    with api.step.nest('cmake'):
      api.third_party_packages.cmake.package()
    with api.step.nest('swig'):
      api.third_party_packages.swig.package()
    with api.step.nest('go'):
      api.third_party_packages.go.package()
    with api.step.nest('firebase'):
      api.third_party_packages.firebase.package()
    with api.step.nest('dep'):
      api.third_party_packages.dep.package()


def GenTests(api):
  def GenTestData():
    platform = 'linux-amd64'
    def cipd_search(parent_step, package_name, version):
      return api.step_data(
          '%s.cipd search %s version:%s' % (
              parent_step, package_name, version),
          api.cipd.example_search(
              package_name,
              instances=0))

    return (
      api.platform.name('linux') +
      api.platform.bits(64) +
      api.step_data('git.refs',
        api.gitiles.make_refs_test_data('refs/tags/v2.12.2.2')) +
      cipd_search(
        'git',
        api.third_party_packages.git.PACKAGE_PREFIX + platform,
        '2.12.2.2' + api.third_party_packages.git.PACKAGE_VERSION_SUFFIX) +
      api.step_data('python.refs',
        api.gitiles.make_refs_test_data('refs/tags/v2.1.2')) +
      cipd_search(
        'python',
        api.third_party_packages.python.PACKAGE_PREFIX + platform,
        '2.1.2' + api.third_party_packages.python.PACKAGE_VERSION_SUFFIX) +
      cipd_search(
        'gcloud',
        api.third_party_packages.gcloud.PACKAGE_TEMPLATE % {
          'platform': platform,
        },
        '1.2.3' + api.third_party_packages.gcloud.PACKAGE_VERSION_SUFFIX) +
      cipd_search(
        'gsutil',
        api.third_party_packages.gsutil.PACKAGE_NAME,
        '4.21' + api.third_party_packages.gsutil.PACKAGE_VERSION_SUFFIX) +
      api.step_data('ninja.refs',
        api.gitiles.make_refs_test_data('refs/tags/v1.7.2')) +
      cipd_search(
        'ninja',
        api.third_party_packages.ninja.PACKAGE_PREFIX + platform,
        '1.7.2' + api.third_party_packages.ninja.PACKAGE_VERSION_SUFFIX) +
      api.step_data('cmake.refs',
        api.gitiles.make_refs_test_data('refs/tags/v3.9.1')) +
      cipd_search(
        'cmake',
        api.third_party_packages.cmake.PACKAGE_PREFIX + platform,
        '3.9.1' + api.third_party_packages.cmake.PACKAGE_VERSION_SUFFIX) +
      api.step_data('swig.refs',
        api.gitiles.make_refs_test_data('refs/tags/rel-3.0.12')) +
      cipd_search(
        'swig',
        api.third_party_packages.swig.PACKAGE_PREFIX + platform,
        '3.0.12' + api.third_party_packages.swig.PACKAGE_VERSION_SUFFIX) +
      cipd_search(
        'go',
        api.third_party_packages.go.PACKAGE_TEMPLATE % {
          'platform': platform,
        },
        '1.2.3' + api.third_party_packages.go.PACKAGE_VERSION_SUFFIX) +
      cipd_search(
        'firebase',
        api.third_party_packages.firebase.PACKAGE_NAME,
        '3.19.3' + api.third_party_packages.firebase.PACKAGE_VERSION_SUFFIX) +
      api.step_data('dep.refs',
        api.gitiles.make_refs_test_data('refs/tags/v0.3.1')) +
      cipd_search(
        'dep',
        api.third_party_packages.dep.PACKAGE_PREFIX + platform,
        '0.3.1' + api.third_party_packages.dep.PACKAGE_VERSION_SUFFIX)
    )

  yield (
      api.test('basic') +
      GenTestData() +
      api.runtime(is_luci=True, is_experimental=False))

  yield (
      api.test('basic-buildbot') +
      GenTestData())

  yield (
      api.test('dry_run') +
      GenTestData() +
      api.runtime(is_luci=True, is_experimental=True))

  yield (
      api.test('cross_compile') +
      api.properties(cross_platform='linux-arm64') +
      GenTestData() +
      api.runtime(is_luci=True, is_experimental=True))
