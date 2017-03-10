# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'build/file',
  'build/zip',
  'depot_tools/cipd',
  'depot_tools/gsutil',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
]


# The GSUtil bucket, all GSUtil packages are stored in here.
GSUTIL_BUCKET = 'gs://pub'

def _gsutil_version(api):
  prefix = '%s/%s' % (GSUTIL_BUCKET, 'gsutil_')

  step_result = api.gsutil.list(
      prefix + '*.zip',
      stdout=api.raw_io.output(),
      step_test_data=lambda:
        api.raw_io.test_api.stream_output('gs://pub/gsutil_4.1.zip'))

  latest_version = None
  for line in step_result.stdout.splitlines():
    if not line.startswith(prefix): # pragma: no cover
      continue

    vstr = line[len(prefix):].rstrip('.zip')
    try:
      version = tuple(int(d) for d in vstr.split('.'))
    except ValueError: # pragma: no cover
      version = ()
    if len(version) == 2 and (not latest_version or latest_version < version):
      latest_version = version

  if not latest_version: # pragma: no cover
    raise Exception('No gsutil version found')

  latest = '.'.join(str(d) for d in latest_version)
  step_result.presentation.step_text += ' %s' % (latest,)
  return latest


def RunSteps(api):
  cipd_pkg_name = 'infra/tools/gsutil'
  cipd_pkg_dir = api.path['start_dir'].join('gsutil')

  # Prepare staging directory to unpack gsutil into.
  staging_dir = api.path['start_dir'].join('gsutil_staging_dir')
  api.file.rmtree('cleaning staging dir', staging_dir)

  try:
    api.cipd.set_service_account_credentials(
        api.cipd.default_bot_service_account_credentials)

    version = _gsutil_version(api)
    name = 'gsutil_%s.zip' % version
    url = '%s/%s' % (GSUTIL_BUCKET, name)
    gsutil_zip = api.path['start_dir'].join(name)

    api.gsutil.download_url(url, gsutil_zip, name='Download %s' % name)
    api.zip.unzip('Unzip %s' % name, gsutil_zip, staging_dir, quiet=True)

    gsutil_dir = staging_dir.join('gsutil')
    api.path.mock_add_paths(gsutil_dir)
    assert api.path.exists(gsutil_dir), (
        'Package directory %s does not exist' % (gsutil_dir))

    # Build and register our CIPD package.
    api.cipd.build(
        input_dir=gsutil_dir,
        output_package=cipd_pkg_dir,
        package_name=cipd_pkg_name,
    )
    api.cipd.register(
        package_name=cipd_pkg_name,
        package_path=cipd_pkg_dir,
        refs=['latest'],
        tags={'gsutil_version': version},
    )
  finally:
    api.file.remove('remove gsutil directory', cipd_pkg_dir)


def GenTests(api):
  yield (
    api.test('linux') +
    api.platform.name('linux') +
    api.properties.generic(path_config='kitchen')
  )
