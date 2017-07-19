# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Packages the Google Cloud SDK for multiple platforms."""

from . import util

from recipe_engine import recipe_api


BASE_URL = 'https://dl.google.com/dl/cloudsdk/channels/rapid'
COMPONENTS_URL = BASE_URL + '/components-2.json'
DOWNLOAD_TEMPLATE = (BASE_URL +
    '/downloads/google-cloud-sdk-%(version)s-%(os)s-%(arch)s%(ext)s')
PACKAGE_TEMPLATE = 'infra/gcloud/%(platform)s'

# This version suffix serves to distinguish different revisions of gcloud built
# with this recipe.
PACKAGE_VERSION_SUFFIX = '.chromium0'


class PlatformNotSupported(Exception):
  pass


class GcloudApi(util.ModuleShim):

  @recipe_api.composite_step
  def package(self, platform_name=None, platform_bits=None):
    platform_name = platform_name or self.m.platform.name
    platform_bits = platform_bits or self.m.platform.bits

    workdir = self.m.path['start_dir'].join('gcloud_%s_%d' % (
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

    # Extract the archive. Always will be named 'google-cloud-sdk'.
    base_dir = workdir.join('google-cloud-sdk')
    self.m.python(
        'extract',
        self.resource('archive_util.py'),
        [archive_path, workdir],
    )

    # Augment the default (installation) properties.
    #
    # NOTE: Currently this builder is OS-agnostic (e.g., a Linux builder can
    # build a Windows package). For now, we will keep it that way by manually
    # updating the properties file.
    #
    # If we ever need to actually run "gcloud" commands to update properties,
    # we can make this packager OS-specific and run "gcloud" in the now-unpacked
    # bundle.
    #
    # Commands are:
    # $ ./bin/gcloud config set  component_manager/disable_update_check true \
    #   --installation
    properties = ''
    properties_file = base_dir.join('properties')
    self.m.path.mock_add_paths(properties_file)
    if self.m.path.exists(properties_file):
      properties = self.m.file.read_text(
          'read instance config',
          properties_file,
          test_data='\n'.join([
              '[core]',
              'disable_usage_reporting = True',
              '',
          ]))
    properties += '\n'.join([
      '',
      '[component_manager]',
      'disable_update_check = true',
    ])
    self.m.file.write_text(
        'write instance config',
        properties_file,
        properties)

    # Create CIPD bundle.
    self.create_package(
        package_name, workdir, base_dir, latest_version, 'copy')


  def _get_latest_version(self, platform_name, platform_bits):
    # Get the latest version of "gcloud". We do this by pulling JSON from
    # the "gcloud" downloading site. The "components-2.json" contains a
    # "version" field that describes the latest "gcloud" version.
    resp = self.m.url.get_json(COMPONENTS_URL, step_name='components',
        default_test_data={'version': '1.2.3'})
    resp.raise_on_error()

    version = resp.output.get('version')
    assert version and isinstance(version, basestring), version

    url = self._get_download_url(version, platform_name, platform_bits)
    self.m.step.active_result.presentation.links['gcloud %r' % (version,)] = (
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
      params['arch'] = 'x86'
    elif platform_bits == 64:
      params['arch'] = 'x86_64'
    else: # pragma: nocover
      raise PlatformNotSupported(
          'Platform bits %r is not supported' % (platform_bits,))

    return DOWNLOAD_TEMPLATE % params
