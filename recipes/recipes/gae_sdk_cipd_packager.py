# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import re


DEPS = [
  'build/gae_sdk',
  'build/zip',
  'depot_tools/cipd',
  'depot_tools/gsutil',
  'recipe_engine/path',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/runtime',
  'recipe_engine/step',
]

def RunSteps(api):
  pb = _PackageBuilder(api)

  # Iterate over all of the GAE SDK packages and build any that don't exist.
  pkg_outdir = api.path.mkdtemp('gae_sdk_package')
  for plat, arch in api.gae_sdk.all_packages:
    with api.step.nest('Sync %s/%s' % (plat, arch,)):
      # Determine the current GAE SDK version.
      try:
        version = pb.latest_upstream_version(plat, arch)
      except pb.VersionParseError as e:
        api.step.active_result.presentation.step_summary_text = str(e)
        api.step.active_result.presentation.status = api.step.FAILURE
        continue

      version_tag = pb.version_tag(version)
      pkg_name = api.gae_sdk.package(plat, arch=arch)
      step = api.cipd.search(pkg_name, '%s:%s' % (version_tag))
      if len(step.json.output['result']) > 0:
        api.python.succeeding_step('Synced', 'Package is up to date.')
        continue

      # Create a temporary directory to build the package in.
      pkg_base = pb.download_and_unpack(plat, arch, version)

      # Build and register our CIPD package.
      pkg_path = pkg_outdir.join('gae_sdk_%s_%s.pkg' % (plat, arch))
      api.cipd.build(
          pkg_base,
          pkg_path,
          pkg_name,
          install_mode='copy',
      )
      api.cipd.register(
          pkg_name,
          pkg_path,
          refs=[api.gae_sdk.latest_ref],
          tags={version_tag[0]: version_tag[1]},
      )


class _PackageBuilder(object):
  # The Google Storage GAE SDK bucket base. All SDK packages are stored in here
  # under a basename + version ZIP file.
  _GS_BUCKET_BASE = 'gs://appengine-sdks/featured'

  class VersionParseError(Exception):
    pass

  def __init__(self, api):
    self._api = api

  def version_tag(self, version):
    return ('gae_sdk_version', version)

  @property
  def api(self):
    return self._api

  def latest_upstream_version(self, plat, arch):
    _, base, _ = self.api.gae_sdk.package_spec(plat, arch)
    prefix = '%s/%s' % (self._GS_BUCKET_BASE, base)

    step_result = self.api.gsutil.list(
        prefix + '*.zip',
        name='Get Latest',
        stdout=self.api.raw_io.output_text())

    latest_version = None
    for line in step_result.stdout.splitlines():
      if not line.startswith(prefix):
        continue

      # gs://..../prefix-#.#.#.zip
      vstr = line[len(prefix):].rstrip('.zip')
      try:
        version = tuple(int(d) for d in vstr.split('.'))
      except ValueError:
        version = ()
      if len(version) == 3 and (not latest_version or latest_version < version):
        latest_version = version

    if not latest_version:
      raise self.VersionParseError('No latest version for prefix: %s' % (
          prefix,))

    latest = '.'.join(str(d) for d in latest_version)
    step_result.presentation.step_text += ' %s' % (latest,)
    return latest

  def download_and_unpack(self, plat, arch, version):
    # Get the package base for this OS.
    _, base, dirname = self.api.gae_sdk.package_spec(plat, arch)
    name = '%s%s.zip' % (base, version)
    artifact_url = '%s/%s' % (self._GS_BUCKET_BASE, name)

    tdir = self.api.path.mkdtemp('gae_sdk')
    dst = tdir.join(name) # Store the ZIP file here.
    unzip_dir = tdir.join('unpack') # Unzip contents here.
    self.api.gsutil.download_url(
        artifact_url,
        dst,
        name='Download %s %s' % (plat, arch,))
    self.api.zip.unzip(
        'Unzip %s %s' % (plat, arch),
        dst,
        unzip_dir,
        quiet=True)

    pkg_dir = unzip_dir.join(dirname)
    self.api.path.mock_add_paths(pkg_dir)
    assert self.api.path.exists(pkg_dir), (
        'Package directory [%s] does not exist' % (pkg_dir,))
    return pkg_dir


def GenTests(api):
  BUCKET_LIST = '\n'.join(
      (_PackageBuilder._GS_BUCKET_BASE + '/' + s)
      for s in (
        'go_appengine_sdk_linux_amd64-1.2.3.zip',
        'go_appengine_sdk_linux_amd64-10.2.3.zip',
        'go_appengine_sdk_linux_amd64-junk.zip',
        'go_appengine_sdk_linux_amd64-99.99.zip',
        'go_appengine_sdk_darwin_amd64-10.2.3.zip',
        'google_appengine_10.2.3.zip',
        'junk',
      ))

  def latest(plat, arch):
    return api.step_data('Sync %s/%s.gsutil Get Latest' % (plat, arch),
          api.raw_io.stream_output(BUCKET_LIST, stream='stdout'))

  def bad_latest(plat, arch):
    return api.step_data('Sync %s/%s.gsutil Get Latest' % (plat, arch),
          api.raw_io.stream_output('foobar', stream='stdout'))

  def cipd_pkg(plat, arch, exists):
    pkg_name = 'infra/gae_sdk/%s/%s' % (plat, arch)
    cipd_step = 'cipd search %s gae_sdk_version:10.2.3' % (pkg_name,)
    instances = (2) if exists else (0)
    return api.step_data('Sync %s/%s.%s' % (plat, arch, cipd_step),
          api.cipd.example_search(pkg_name, instances=instances))

  runtime = api.runtime(is_luci=True, is_experimental=False)

  packages_test = api.test('packages') + runtime
  bad_version_test = api.test('bad_version_list') + runtime
  for plat, arch, exists in (
      ('go', 'linux-amd64', False),
      ('go', 'mac-amd64', True),
      ('python', 'all', False)):
    packages_test += (
        latest(plat, arch) +
        cipd_pkg(plat, arch, exists))
    bad_version_test += bad_latest(plat, arch)

  yield packages_test
  yield bad_version_test
