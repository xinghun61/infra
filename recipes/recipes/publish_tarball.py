# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api

DEPS = [
  'bot_update',
  'chromium',
  'file',
  'gclient',
  'gsutil',
  'omahaproxy',
  'path',
  'platform',
  'properties',
  'python',
  'raw_io',
  'step',
  'trigger',
]


def gsutil_upload(api, source, bucket, dest, args):
  api.gsutil.upload(source, bucket, dest, args, name=str('upload ' + dest))


@recipe_api.composite_step
def export_tarball(api, args, source, destination):
  try:
    temp_dir = api.path.mkdtemp('export_tarball')
    api.python(
        'export_tarball',
        api.chromium.resource('export_tarball.py'),
        args,
        cwd=temp_dir)
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
    api.file.rmtree('temp dir', temp_dir)


@recipe_api.composite_step
def export_lite_tarball(api, version):
  try:
    temp_dir = api.path.mkdtemp('lite_tarball')
    dest_dir = api.path.join(temp_dir, 'src')

    # Make destructive file operations on the copy of the checkout.
    api.file.copytree('copytree', api.path['checkout'], dest_dir, symlinks=True)

    directories = [
      'native_client',
      'native_client_sdk',
      'third_party/WebKit/ManualTests',
      'third_party/WebKit/PerformanceTests',
      'third_party/android_platform',
      'third_party/chromite',
      'third_party/freetype2',
      'third_party/gles2_book',
      'third_party/gold',
      'third_party/icu',
      'third_party/launchpad_translations',
      'third_party/libc++',
      'third_party/libevent',
      'third_party/libjpeg_turbo',
      'third_party/libmtp',
      'third_party/libxml/src',
      'third_party/openssl',
      'third_party/snappy',
      'third_party/webgl',
      'third_party/webgl_conformance',
      'third_party/yasm',
      'tools/win',
      'v8/third_party/icu',
    ]
    for directory in directories:
      try:
        api.step('prune %s' % directory, [
            'find', api.path.join(dest_dir, directory), '-type', 'f',
            '!', '-iname', '*.gyp*',
            '!', '-iname', '*.isolate*',
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
  finally:
    api.file.rmtree('temp dir', temp_dir)


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
        min_major_version=43, exclude_platforms=['ios']):
      if 'chromium-%s.tar.xz' % release['version'] not in ls_result:
        missing_releases.add(release['version'])
    for version in missing_releases:
      api.trigger({'buildername': 'publish_tarball', 'version': version})
    return

  version = api.properties['version']

  api.gclient.set_config('chromium')
  solution = api.gclient.c.solutions[0]
  solution.revision = 'refs/tags/%s' % version
  api.bot_update.ensure_checkout(force=True, with_branch_heads=True)

  with api.step.defer_results():
    # Export full tarball.
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

    # Export test data.
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

    export_lite_tarball(api, version)


def GenTests(api):
  yield (
    api.test('basic') +
    api.properties.generic(version='38.0.2125.122') +
    api.platform('linux', 64)
  )

  yield (
    api.test('trigger') +
    api.properties.generic() +
    api.platform('linux', 64) +
    api.step_data('gsutil ls', stdout=api.raw_io.output(''))
  )
