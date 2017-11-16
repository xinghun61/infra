# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Packages the gsutil for multiple platforms."""

from . import util

from recipe_engine import recipe_api


VERSION_URL = ('https://raw.githubusercontent.com' +
    '/GoogleCloudPlatform/gsutil/master/VERSION')
DOWNLOAD_TEMPLATE = 'https://storage.googleapis.com/pub/gsutil_%s.tar.gz'
PACKAGE_NAME = 'infra/gsutil'

# This version suffix serves to distinguish different revisions of gsutil built
# with this recipe.
PACKAGE_VERSION_SUFFIX = ''


class PlatformNotSupported(Exception):
  pass


class GsutilApi(util.ModuleShim):

  @recipe_api.composite_step
  def package(self):
    if not self.m.platform.is_linux: # no cover
      self.m.python.succeeding_step('Only built on Linux', 'No need.')
      return

    workdir = self.m.path['start_dir'].join('gsutil')
    self.m.file.ensure_directory('workdir', workdir)

    latest_version, download_url = self._get_latest_version()
    latest_version += PACKAGE_VERSION_SUFFIX

    if self.does_package_exist(PACKAGE_NAME, latest_version):
      self.m.python.succeeding_step('Synced', 'Package is up to date.')
      return

    # Download the package data.
    archive_path = workdir.join(download_url[download_url.rfind('/')+1:])
    resp = self.m.url.get_file(download_url, archive_path, step_name='download')
    resp.raise_on_error()

    # Extract the archive. Always will be named 'gsutil'.
    base_dir = workdir.join('gsutil')
    self.m.python(
        'extract',
        self.resource('archive_util.py'),
        [archive_path, workdir],
    )

    # Create CIPD bundle.
    package_file = self.build_package(PACKAGE_NAME, workdir, base_dir, 'copy')
    self.register_package(package_file, PACKAGE_NAME, latest_version)


  def _get_latest_version(self):
    # Get the latest version of "gsutil". We do this by checking the VERSION
    # file in the gsutil Git repository on GitHub.
    resp = self.m.url.get_text(VERSION_URL, step_name='version',
        default_test_data='4.21\n')
    resp.raise_on_error()

    version = resp.output.strip()
    assert version is not None

    url = DOWNLOAD_TEMPLATE % version
    self.m.step.active_result.presentation.links['gsutil %r' % (version,)] = (
        url)
    return version, url
