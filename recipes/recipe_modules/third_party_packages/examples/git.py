# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe for 'git' building.

During testing, it may be useful to focus on building Git. This can be done by
running this recipe module directly.
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
    'refs/tags/v2.12.2.2',
]


WINDOWS_RELEASE = {
  'assets': [
    {
      'url': (
          'https://api.github.com/repos/git-for-windows/git/releases/assets/'
          '3580732'),
      'name': 'PortableGit-2.12.2.2-32-bit.7z.exe',
    },
    {
      'url': (
          'https://api.github.com/repos/git-for-windows/git/releases/assets/'
          '3580733'),
      'name': 'PortableGit-2.12.2.2-64-bit.7z.exe',
    },
  ]
}


def RunSteps(api, dry_run):
  api.third_party_packages.dry_run = dry_run
  if not dry_run:
    api.cipd.set_service_account_credentials(
        api.cipd.default_bot_service_account_credentials)

  api.third_party_packages.git.package()


def GenTests(api):
  git = api.third_party_packages.git
  test_refs = api.gitiles.make_refs_test_data(*REFS)

  def GenTest(platform_name, bits, platform_suffix, exists=False):
    package_name = git.PACKAGE_PREFIX + platform_suffix
    package_tag = 'version:%s%s' % ('2.12.2.2', git.PACKAGE_VERSION_SUFFIX)
    test_data = (
        api.platform.name(platform_name) +
        api.platform.bits(bits) +
        api.properties(dry_run=False) +
        api.override_step_data(
            'cipd search %s %s' % (package_name, package_tag),
            api.cipd.example_search(
                package_name,
                instances=(1 if exists else 0)))
    )
    if platform_name != 'win':
      test_data += api.step_data('refs', test_refs)
    else:
      test_data += api.url.json(
          'get latest release',
          WINDOWS_RELEASE)
      if not exists:
        test_data += api.step_data('post-install', retcode=1)
    return test_data

  for platform_name, bits, platform_suffix in PLATFORMS:
    test = api.test('new_on_%s' % (platform_suffix,))
    test += GenTest(platform_name, bits, platform_suffix)
    yield test

  yield (
      api.test('mac_exists') +
      api.properties(dry_run=False) +
      GenTest('mac', 64, 'mac-amd64', exists=True)
  )

  yield (
      api.test('windows_exists') +
      api.properties(dry_run=False) +
      GenTest('win', 64, 'windows-amd64', exists=True)
  )

  yield (
      api.test('mac_specific_tag') +
      api.platform.name('mac') +
      api.platform.bits(64) +
      api.properties(dry_run=False) +
      api.properties(git_release_tag='v2.12.2')
  )

  yield (
      api.test('dry_run') +
      api.platform.name('linux') +
      api.platform.bits(64) +
      api.step_data('refs', test_refs)
  )
