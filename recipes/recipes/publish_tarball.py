# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=line-too-long

from recipe_engine import recipe_api

import contextlib

DEPS = [
  'build/chromium',
  'build/trigger',
  'depot_tools/bot_update',
  'depot_tools/depot_tools',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/gsutil',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'omahaproxy',
]

# Sometimes a revision will be bad because the checkout will fail, causing
# publish_tarball to fail.  The version will stay in the omaha version list for
# several months and publish_tarball will keep re-running on the same broken
# version.  This blacklist exists to exclude those broken versions so the bot
# doesn't keep retrying and sending build failure emails out.
BLACKLISTED_VERSIONS = [
    '67.0.3376.0',
    '67.0.3376.1',
]

def gsutil_upload(api, source, bucket, dest, args):
  api.gsutil.upload(source, bucket, dest, args, name=str('upload ' + dest))


def published_full_tarball(version, ls_result):
  return 'chromium-%s.tar.xz' % version in ls_result


def published_lite_tarball(version, ls_result):
  return 'chromium-%s-lite.tar.xz' % version in ls_result


def published_test_tarball(version, ls_result):
  return 'chromium-%s-testdata.tar.xz' % version in ls_result


def published_nacl_tarball(version, ls_result):
  return 'chromium-%s-nacl.tar.xz' % version in ls_result


def published_all_tarballs(version, ls_result):
  return (published_full_tarball(version, ls_result) and
          published_lite_tarball(version, ls_result) and
          published_test_tarball(version, ls_result) and
          published_nacl_tarball(version, ls_result))


@recipe_api.composite_step
def export_tarball(api, args, source, destination):
  try:
    temp_dir = api.path.mkdtemp('export_tarball')
    with api.context(cwd=temp_dir):
      api.python(
          'export_tarball',
          api.chromium.resource('export_tarball.py'),
          args)
    gsutil_upload(
        api,
        api.path.join(temp_dir, source),
        'chromium-browser-official',
        destination,
        args=['-a', 'public-read'])

    hashes_result = api.python(
        'generate_hashes',
        api.chromium.resource('generate_hashes.py'),
        [api.path.join(temp_dir, source), api.raw_io.output()],
        step_test_data=lambda: api.raw_io.test_api.output(
            'md5  164ebd6889588da166a52ca0d57b9004  bash'))
    gsutil_upload(
        api,
        api.raw_io.input(hashes_result.raw_io.output),
        'chromium-browser-official',
        destination + '.hashes',
        args=['-a', 'public-read'])
  finally:
    api.file.rmtree('rmtree temp dir', temp_dir)


@contextlib.contextmanager
def copytree_checkout(api):
  try:
    temp_dir = api.path.mkdtemp('tmp')
    dest_dir = api.path.join(temp_dir, 'src')
    api.file.copytree('copytree', api.path['checkout'], dest_dir, symlinks=True)
    yield dest_dir
  finally:
    api.file.rmtree('rmtree temp dir', temp_dir)


@recipe_api.composite_step
def export_lite_tarball(api, version):
  # Make destructive file operations on the copy of the checkout.
  with copytree_checkout(api) as dest_dir:
    directories = [
      'android_webview',
      'buildtools/third_party/libc++',
      'chrome/android',
      'chromecast',
      'ios',
      'native_client',
      'native_client_sdk',
      'third_party/android_platform',
      'third_party/chromite',
      'third_party/closure_compiler',
      'third_party/freetype',
      'third_party/icu',
      'third_party/libjpeg_turbo',
      'third_party/libxml/src',
      'third_party/snappy',
      'third_party/webgl',
      'third_party/yasm',
      'tools/win',
    ]
    # We're moving these directories. Try to prune a directory only if
    # it exists. crbug.com/829695
    for directory in ['third_party/WebKit/ManualTests',
                      'third_party/WebKit/PerformanceTests',
                      'third_party/blink/manual_tests',
                      'third_party/blink/perf_tests']:
      if api.path.exists(api.path.join(dest_dir, directory)):
        directories.append(directory)  # pragma: no cover

    for directory in directories:
      try:
        api.step('prune %s' % directory, [
            'find', api.path.join(dest_dir, directory), '-type', 'f',
            '!', '-iname', '*.gyp*',
            '!', '-iname', '*.gn*',
            '!', '-iname', '*.isolate*',
            '!', '-iname', '*.grd*',
            # This file is required for Linux afdo builds.
            '!', '-path',
            api.path.join(dest_dir, 'chrome/android/profiles/afdo.prof'),
            '-delete'])
      except api.step.StepFailure:  # pragma: no cover
        # Ignore failures to delete these directories - they can be inspected
        # later to see whether they have moved to a different location
        # or deleted in different versions of the codebase.
        pass

    # Empty directories take up space in the tarball.
    api.step('prune empty directories', [
        'find', dest_dir, '-depth', '-type', 'd', '-empty', '-delete'])

    export_tarball(
        api,
        # Verbose output helps avoid a buildbot timeout when no output
        # is produced for a long time.
        ['--remove-nonessential-files',
         'chromium-%s' % version,
         '--verbose',
         '--progress',
         '--src-dir', dest_dir],
        'chromium-%s.tar.xz' % version,
        'chromium-%s-lite.tar.xz' % version)


@recipe_api.composite_step
def export_nacl_tarball(api, version):
  # Make destructive file operations on the copy of the checkout.
  with copytree_checkout(api) as dest_dir:
    # Based on instructions from https://sites.google.com/a/chromium.org/dev/nativeclient/pnacl/building-pnacl-components-for-distribution-packagers
    api.python(
        'download pnacl toolchain dependencies',
        api.path.join(dest_dir, 'native_client', 'toolchain_build',
                      'toolchain_build_pnacl.py'),
        ['--verbose', '--sync', '--sync-only', '--disable-git-cache'])

    export_tarball(
        api,
        # Verbose output helps avoid a buildbot timeout when no output
        # is produced for a long time.
        ['--remove-nonessential-files',
         'chromium-%s' % version,
         '--verbose',
         '--progress',
         '--src-dir', dest_dir],
        'chromium-%s.tar.xz' % version,
        'chromium-%s-nacl.tar.xz' % version)


def RunSteps(api):
  if 'version' not in api.properties:
    ls_result = api.gsutil(['ls', 'gs://chromium-browser-official/'],
                           stdout=api.raw_io.output()).stdout
    missing_releases = set()
    # TODO(phajdan.jr): find better solution than hardcoding version number.
    # We do that currently (carryover from a solution this recipe is replacing)
    # to avoid running into errors with older releases.
    # Exclude ios - it often uses internal buildspecs so public ones don't work.
    for release in api.omahaproxy.history(
        min_major_version=66, exclude_platforms=['ios']):
      if release['channel'] not in ('stable', 'beta', 'dev', 'canary'):
        continue
      version = release['version']
      if not published_all_tarballs(version, ls_result):
        missing_releases.add(version)
    for version in missing_releases:
      if version not in BLACKLISTED_VERSIONS:
        api.trigger({'buildername': 'publish_tarball', 'version': version})
    return

  version = api.properties['version']

  ls_result = api.gsutil(['ls', 'gs://chromium-browser-official/'],
                         stdout=api.raw_io.output()).stdout
  if published_all_tarballs(version, ls_result):
    return

  api.gclient.set_config('chromium')
  solution = api.gclient.c.solutions[0]
  solution.revision = 'refs/tags/%s' % version
  api.bot_update.ensure_checkout(
      with_branch_heads=True, with_tags=True, suffix=version)

  api.git('clean', '-dffx')
  with api.context(cwd=api.path['checkout']):
    api.gclient('sync', ['sync', '-D', '--nohooks', '--with_branch_heads',
                         '--with_tags'])

  api.step(
      'touch chrome/test/data/webui/i18n_process_css_test.html',
      ['touch', api.path['checkout'].join(
          'chrome', 'test', 'data', 'webui', 'i18n_process_css_test.html')])

  if int(version.split('.')[0]) >= 65:
    api.step('download clang sources', [
        api.path['checkout'].join('tools', 'clang', 'scripts', 'update.py'),
        '--force-local-build', '--without-android', '--use-system-cmake',
        '--if-needed', '--gcc-toolchain=/usr', '--skip-build'])

  api.python('fetch android AFDO profile', api.path['checkout'].join(
      'chrome', 'android', 'profiles', 'update_afdo_profile.py'), [])

  node_modules_sha_path = api.path['checkout'].join(
      'third_party', 'node', 'node_modules.tar.gz.sha1')
  if api.path.exists(node_modules_sha_path):
    api.python(
        'webui_node_modules',
        api.depot_tools.download_from_google_storage_path,
        [
            '--no_resume',
            '--extract',
            '--no_auth',
            '--bucket', 'chromium-nodejs',
            '-s', node_modules_sha_path,
        ]
    )

  with api.step.defer_results():
    if not published_full_tarball(version, ls_result):
      export_tarball(
          api,
          # Verbose output helps avoid a buildbot timeout when no output
          # is produced for a long time.
          ['--remove-nonessential-files',
           'chromium-%s' % version,
           '--verbose',
           '--progress',
           '--src-dir', api.path['checkout']],
          'chromium-%s.tar.xz' % version,
          'chromium-%s.tar.xz' % version)

      # Trigger a tarball build now that the full tarball has been uploaded.
      api.trigger({
          'builder_name': 'Build From Tarball',
          'properties': {'version': version},
      })

    if not published_test_tarball(version, ls_result):
      export_tarball(
          api,
          # Verbose output helps avoid a buildbot timeout when no output
          # is produced for a long time.
          ['--test-data',
           'chromium-%s' % version,
           '--verbose',
           '--progress',
           '--src-dir', api.path['checkout']],
          'chromium-%s.tar.xz' % version,
          'chromium-%s-testdata.tar.xz' % version)

    if not published_lite_tarball(version, ls_result):
      export_lite_tarball(api, version)

    if not published_nacl_tarball(version, ls_result):
      export_nacl_tarball(api, version)


def GenTests(api):
  yield (
    api.test('basic') +
    api.properties.generic(version='69.0.3446.0') +
    api.platform('linux', 64) +
    api.step_data('gsutil ls', stdout=api.raw_io.output('')) +
    api.path.exists(api.path['checkout'].join(
        'third_party', 'node', 'node_modules.tar.gz.sha1'))
  )

  yield (
    api.test('dupe') +
    api.properties.generic(version='69.0.3446.0') +
    api.platform('linux', 64) +
    api.step_data('gsutil ls', stdout=api.raw_io.output(
        'gs://chromium-browser-official/chromium-69.0.3446.0.tar.xz\n'
        'gs://chromium-browser-official/chromium-69.0.3446.0-lite.tar.xz\n'
        'gs://chromium-browser-official/chromium-69.0.3446.0-testdata.tar.xz\n'
        'gs://chromium-browser-official/chromium-69.0.3446.0-nacl.tar.xz\n'
    ))
  )

  yield (
    api.test('trigger') +
    api.properties.generic() +
    api.platform('linux', 64) +
    api.step_data('gsutil ls', stdout=api.raw_io.output(''))
  )
