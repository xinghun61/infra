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
  'recipe_engine/step',
  'third_party_packages',
]

PROPERTIES = {
  'dry_run': Property(default=False, kind=bool),
}


def RunSteps(api, dry_run):
  api.third_party_packages.dry_run = dry_run
  if not dry_run:
    api.cipd.set_service_account_credentials(
        api.cipd.default_bot_service_account_credentials)

  with api.step.defer_results():
    with api.step.nest('python'):
      api.third_party_packages.python.package()
    with api.step.nest('git'):
      api.third_party_packages.git.package()
    with api.step.nest('gcloud'):
      api.third_party_packages.gcloud.package()
    with api.step.nest('ninja'):
      api.third_party_packages.ninja.package()


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
      api.step_data('ninja.refs',
        api.gitiles.make_refs_test_data('refs/tags/v1.7.2')) +
      cipd_search(
        'ninja',
        api.third_party_packages.ninja.PACKAGE_PREFIX + platform,
        '1.7.2' + api.third_party_packages.ninja.PACKAGE_VERSION_SUFFIX)
    )

  yield (
      api.test('basic') +
      GenTestData())

  yield (
      api.test('dry_run') +
      GenTestData() +
      api.properties(dry_run=True)
  )
