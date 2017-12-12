# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
"""Recipe for Go dependency management tool building.

During testing, it may be useful to focus on building dep. This can be done
by running this recipe module directly.
"""

from recipe_engine.recipe_api import Property


DEPS = [
  'depot_tools/cipd',
  'depot_tools/gitiles',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/url',
  'third_party_packages',
]


PROPERTIES = {
    'dry_run': Property(default=True, kind=bool),
}


PLATFORMS = (
    ('linux', 32, 'linux-386'),
    ('linux', 64, 'linux-amd64'),
    ('mac', 64, 'mac-amd64'),
    ('win', 32, 'windows-386'),
    ('win', 64, 'windows-amd64'),
)


REFS = [
    'HEAD',
    'refs/heads/master',
    'refs/tags/v0.3.0',
    'refs/tags/v0.3.1',
    'refs/tags/v0.3.2',
]


def RunSteps(api, dry_run):
  api.third_party_packages.dry_run = dry_run
  if not dry_run:
    api.cipd.set_service_account_credentials(
        api.cipd.default_bot_service_account_credentials)

  api.third_party_packages.dep.package()



def GenTests(api):
  dep = api.third_party_packages.dep
  test_refs = api.gitiles.make_refs_test_data(*REFS)
  version = '0.3.2' + dep.PACKAGE_VERSION_SUFFIX

  for name, bits, platform in PLATFORMS:
    package_name = dep.PACKAGE_PREFIX + platform
    yield (
        api.test('%s_%d' % (name, bits)) +
        api.platform(name, bits) +
        api.properties(dry_run=False) +
        api.step_data(
            'cipd search %s version:%s' % (package_name, version),
            api.cipd.example_search(package_name, instances=0)) +
        api.step_data('refs', test_refs)
    )

  package_name = dep.PACKAGE_PREFIX + 'linux-386'
  yield (
      api.test('exists') +
      api.platform('linux', 32) +
      api.properties(dry_run=False) +
      api.step_data(
          'cipd search %s version:%s' % (package_name, version),
          api.cipd.example_search(package_name, instances=1)) +
      api.step_data('refs', test_refs)
  )
