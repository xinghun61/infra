# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe for 'python' building.

During testing, it may be useful to focus on building Python. This can be done
by running this recipe module directly.
"""

from recipe_engine.recipe_api import Property


DEPS = [
  'depot_tools/cipd',
  'depot_tools/gitiles',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'third_party_packages',
]

PROPERTIES = {
  'dry_run': Property(default=True, kind=bool),
}


PLATFORMS = (
  ('linux', 64, 'linux-amd64'),
  ('linux', 32, 'linux-386'),
  ('mac', 64, 'mac-amd64'),
  ('win', 64, 'windows-amd64'),
  ('win', 32, 'windows-386'),
)


REFS = [
    'HEAD',
    'refs/heads/master',
    'refs/tags/not-a-version',
    'refs/tags/v2.1.1',
    'refs/tags/v2.1.2',
    'refs/tags/v2.1.3rc1',
    'refs/tags/v3.0.0',
]


def RunSteps(api, dry_run):
  api.third_party_packages.dry_run = dry_run
  if not dry_run:
    api.cipd.set_service_account_credentials(
        api.cipd.default_bot_service_account_credentials)

  api.third_party_packages.python.package()


def GenTests(api):
  python = api.third_party_packages.python

  def GenTest(platform_name, bits, platform_suffix, exists=False):
    package_name = python.PACKAGE_PREFIX + platform_suffix
    test_data = (
        api.platform.name(platform_name) +
        api.platform.bits(bits) +
        api.properties(dry_run=False)
    )
    if platform_name != 'win':
      test_data += api.step_data('refs', api.gitiles.make_refs_test_data(*REFS))
      test_data += api.override_step_data(
          'cipd search %s version:2.1.2%s' % (
            package_name, python.PACKAGE_VERSION_SUFFIX),
          api.cipd.example_search(
              package_name,
              instances=(1 if exists else 0))
      )

    return test_data

  for (platform_name, bits, platform_suffix) in PLATFORMS:
    test = api.test('new_on_%s' % (platform_suffix,))
    test += GenTest(platform_name, bits, platform_suffix)
    yield test

  yield (
      api.test('mac_exists') +
      GenTest('mac', 64, 'mac-amd64', exists=True)
  )

  yield (
      api.test('mac_failure') +
      GenTest('mac', 64, 'mac-amd64') +
      api.step_data('make', retcode=1)
  )
