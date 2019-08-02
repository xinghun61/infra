# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'cloudbuildhelper',
  'recipe_engine/json',
]


def RunSteps(api):
  # With all args.
  img = api.cloudbuildhelper.build(
      manifest='some/dir/target.yaml',
      canonical_tag='123_456',
      build_id='bid',
      infra='dev',
      labels={'l1': 'v1', 'l2': 'v2'},
      tags=['latest', 'another'],
  )

  expected = api.cloudbuildhelper.Image(
      image='example.com/fake-registry/target',
      digest='sha256:34a04005bcaf206e...',
      tag='123_456')
  assert img == expected, img

  # With minimal args and custom emulated output.
  custom = api.cloudbuildhelper.Image(
      image='xxx',
      digest='yyy',
      tag=None)
  img = api.cloudbuildhelper.build('another.yaml', step_test_image=custom)
  assert img == custom, img

  # Using non-canonical tag.
  api.cloudbuildhelper.build('a.yaml', tags=['something'])

  # Use custom binary from this point onward, for test coverage.
  api.cloudbuildhelper.command = 'custom_cloudbuildhelper'

  # Image that wasn't uploaded anywhere.
  img = api.cloudbuildhelper.build(
      'third.yaml', step_test_image=api.cloudbuildhelper.NotUploadImage)
  assert img == api.cloudbuildhelper.NotUploadImage, img

  # Possibly failing build.
  api.cloudbuildhelper.build('fail_maybe.yaml')


def GenTests(api):
  yield api.test('simple')

  yield (
      api.test('failing') +
      api.step_data(
          'cloudbuildhelper build fail_maybe',
          api.cloudbuildhelper.error_output('Boom'),
          retcode=1)
  )
