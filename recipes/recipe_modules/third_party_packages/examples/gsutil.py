# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
"""Recipe for gsutil building.

During testing, it may be useful to focus on building the gsutil. This can be
done by running this recipe module directly.
"""

from recipe_engine.recipe_api import Property


DEPS = [
  'depot_tools/cipd',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/url',
  'third_party_packages',
]


PROPERTIES = {
    'dry_run': Property(default=True, kind=bool),
}


def RunSteps(api, dry_run):
  api.third_party_packages.dry_run = dry_run
  if not dry_run:
    api.cipd.set_service_account_credentials(
        api.cipd.default_bot_service_account_credentials)

  api.third_party_packages.gsutil.package()


def GenTests(api):
  gsutil = api.third_party_packages.gsutil
  version = '4.21' + gsutil.PACKAGE_VERSION_SUFFIX

  yield (
      api.test('linux') +
      api.properties(
        dry_run=False,
      ) +
      api.step_data(
          'cipd search %s version:%s' % (gsutil.PACKAGE_NAME, version),
          api.cipd.example_search(gsutil.PACKAGE_NAME, instances=0))
  )

  yield (
      api.test('linux_exists') +
      api.properties(
        dry_run=False,
      ) +
      api.step_data(
          'cipd search %s version:%s' % (gsutil.PACKAGE_NAME, version),
          api.cipd.example_search(gsutil.PACKAGE_NAME, instances=1))
  )

  yield (
      api.test('windows_skip') +
      api.platform('win', 64) +
      api.properties(dry_run=False)
  )

  yield (
      api.test('mac_skip') +
      api.platform('mac', 64) +
      api.properties(dry_run=False)
  )
