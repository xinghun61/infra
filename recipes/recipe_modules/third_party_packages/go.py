# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Packages the Go toolchain for multiple platforms."""

from . import util

from recipe_engine import recipe_api


VERSION_URL = 'https://golang.org/VERSION?m=text'
BASE_URL = 'https://storage.googleapis.com/golang'
DOWNLOAD_TEMPLATE = (BASE_URL +
    '/go%(version)s.%(os)s-%(arch)s%(ext)s')
PACKAGE_TEMPLATE = 'infra/go/%(platform)s'

# This version suffix serves to distinguish different revisions of go built
# with this recipe.
PACKAGE_VERSION_SUFFIX = ''


class PlatformNotSupported(Exception):
  pass


class GoApi(util.ModuleShim):

  @recipe_api.composite_step
  def package(self, platform_name=None, platform_bits=None):
    platform_name = platform_name or self.m.platform.name
    platform_bits = platform_bits or self.m.platform.bits

    workdir = self.m.path['start_dir'].join('go_%s_%d' % (
        platform_name, platform_bits))
    self.m.file.ensure_directory('workdir', workdir)

    latest_version, download_url = self._get_latest_version(
        platform_name, platform_bits)
    latest_version += PACKAGE_VERSION_SUFFIX

    package_name = PACKAGE_TEMPLATE % {
        'platform': self.m.cipd.platform_suffix(
            name=platform_name,
            bits=platform_bits,
        ),
    }
    if self.does_package_exist(package_name, latest_version):
      self.m.python.succeeding_step('Synced', 'Package is up to date.')
      return

    # Download the package data.
    archive_path = workdir.join(download_url[download_url.rfind('/')+1:])
    resp = self.m.url.get_file(download_url, archive_path, step_name='download')
    resp.raise_on_error()

    # Extract the archive. Always will be named 'go'.
    base_dir = workdir.join('go')
    self.m.python(
        'extract',
        self.resource('archive_util.py'),
        [archive_path, workdir],
    )

    # Create CIPD bundle.
    package_file = self.build_package(package_name, workdir, base_dir, 'copy')
    self.register_package(package_file, package_name, latest_version)


  def _get_latest_version(self, platform_name, platform_bits):
    # Get the latest version of Go. We do this by checking the build version
    # on the Go front page.
    resp = self.m.url.get_text(VERSION_URL, step_name='version',
        default_test_data='go1.2.3')
    resp.raise_on_error()

    assert resp.output and resp.output.startswith("go")
    version = resp.output[2:]

    url = self._get_download_url(version, platform_name, platform_bits)
    self.m.step.active_result.presentation.links['go %r' % (version,)] = (
        url)
    return version, url


  @staticmethod
  def _get_download_url(version, platform_name, platform_bits):
    params = {
        'version': version,
    }
    if platform_name == 'linux':
      params['os'] = 'linux'
      params['ext'] = '.tar.gz'
    elif platform_name == 'mac':
      params['os'] = 'darwin'
      params['ext'] = '.tar.gz'
    elif platform_name == 'win':
      params['os'] = 'windows'
      params['ext'] = '.zip'
    else: # pragma: nocover
      raise PlatformNotSupported(
          'Platform %r is not supported' % (platform_name,))

    if platform_bits == 32:
      params['arch'] = '386'
    elif platform_bits == 64:
      params['arch'] = 'amd64'
    else: # pragma: nocover
      raise PlatformNotSupported(
          'Platform bits %r is not supported' % (platform_bits,))

    return DOWNLOAD_TEMPLATE % params
