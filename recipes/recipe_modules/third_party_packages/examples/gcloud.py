# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
"""Recipe for Google Cloud SDK building.

During testing, it may be useful to focus on building the SDK. This can be done
by running this recipe module directly.
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
    'platform_name': Property(default=None, kind=str),
    'platform_bits': Property(default=None, kind=int),
    'dry_run': Property(default=True, kind=bool),
}


PLATFORMS = (
    ('linux', 32, 'linux-386'),
    ('linux', 64, 'linux-amd64'),
    ('mac', 64, 'mac-amd64'),
    ('win', 32, 'windows-386'),
    ('win', 64, 'windows-amd64'),
)


def RunSteps(api, platform_name, platform_bits, dry_run):
  api.third_party_packages.dry_run = dry_run
  if not dry_run:
    api.cipd.set_service_account_credentials(
        api.cipd.default_bot_service_account_credentials)

  api.third_party_packages.gcloud.package(
      platform_name=platform_name,
      platform_bits=platform_bits)



def GenTests(api):
  gcloud = api.third_party_packages.gcloud
  version = '1.2.3' + gcloud.PACKAGE_VERSION_SUFFIX

  for name, bits, platform in PLATFORMS:
    package_name = gcloud.PACKAGE_TEMPLATE % {'platform': platform}
    yield (
        api.test('%s_%d' % (name, bits)) +
        api.platform('linux', 32) +
        api.properties(
          platform_name=name,
          platform_bits=bits,
          dry_run=False,
        ) +
        api.step_data(
            'cipd search %s version:%s' % (package_name, version),
            api.cipd.example_search(package_name, instances=0))
    )

  package_name = gcloud.PACKAGE_TEMPLATE % {'platform': 'linux-386'}
  yield (
      api.test('exists') +
      api.platform('linux', 32) +
      api.properties(
        dry_run=False,
      ) +
      api.step_data(
          'cipd search %s version:%s' % (package_name, version),
          api.cipd.example_search(package_name, instances=1))
  )
