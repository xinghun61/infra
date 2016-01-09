# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe to build CIPD package with sealed Conda environment.

Supposed to be used from manually triggered Buildbot builders. We aren't
expecting rebuilding this environment often, so setting up and periodic schedule
is a waste of resources.

To build a new package for all platforms:
1. Manually trigger all builders by clicking buttons in Buildbot.
2. Once they all complete, tag the with some release identifier by running:
    ./cipd set-tag infra/conda_python/scientific/ \
        -tag=release:<name> \
        -version=latest
3. Update Puppet configs to use 'release:<name>' as a version.
"""

DEPS = [
  'cipd',
  'conda',
  'file',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
]


# See https://repo.continuum.io/miniconda/. Miniconda3 is not supported.
CONDA_VERSION = 'Miniconda2-3.18.3'


# These conda packages will be installed into Conda environment.
EXTRA_CONDA_PACKAGES = [
  'matplotlib',
  'numpy',
  'scipy',
]


def RunSteps(api):
  api.cipd.install_client()
  cipd_pkg_name = 'infra/conda_python/scientific/' + api.cipd.platform_suffix()
  cipd_pkg_file = api.path['slave_build'].join('conda_python.cipd')

  # Prepare staging directory to install conda into.
  staging_dir = api.path['slave_build'].join('conda_staging_dir')
  api.file.rmtree('cleaning staging dir', staging_dir)

  # Install miniconda and all Conda packages, package in CIPD and upload.
  with api.conda.install(CONDA_VERSION, staging_dir) as conda:
    for pkg in EXTRA_CONDA_PACKAGES:
      conda.install(pkg)
    try:
      conda.convert_to_cipd_package(cipd_pkg_name, cipd_pkg_file)
      if api.platform.is_win:
        creds = 'C:\\creds\\service_accounts\\service-account-cipd-builder.json'
      else:
        creds = '/creds/service_accounts/service-account-cipd-builder.json'
      api.cipd.set_service_account_credentials(creds)
      tags = {
        'buildbot_build': '%s/%s/%s' % (
            api.properties['mastername'],
            api.properties['buildername'],
            api.properties['buildnumber']),
        'conda': CONDA_VERSION.replace('.', '-'),
      }
      api.cipd.register(
          package_name=cipd_pkg_name,
          package_path=cipd_pkg_file,
          refs=['latest'],
          tags=tags)
    finally:
      api.file.remove('remove *.cipd file', cipd_pkg_file)


def GenTests(api):
  yield (
    api.test('linux') +
    api.platform.name('linux') +
    api.properties.generic()
  )
  yield (
    api.test('mac') +
    api.platform.name('mac') +
    api.properties.generic()
  )
  yield (
    api.test('win') +
    api.platform.name('win') +
    api.properties.generic()
  )
