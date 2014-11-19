# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'bot_update',
  'gclient',
  'gsutil',
  'path',
  'platform',
  'properties',
  'python',
]


def export_tarball(api, args, source, destination):
  try:
    temp_dir = api.path.mkdtemp('export_tarball')
    api.python(
        'export_tarball',
        api.path['checkout'].join(
            'tools', 'export_tarball', 'export_tarball.py'),
        args,
        cwd=temp_dir)
    api.gsutil.upload(
        api.path.join(temp_dir, source),
        'chromium-browser-official',
        destination)
  finally:
    api.path.rmtree('temp dir', temp_dir)


def GenSteps(api):
  version = api.properties['version']

  api.gclient.set_config('chromium')
  solution = api.gclient.c.solutions[0]
  solution.revision = 'refs/tags/%s' % version
  api.bot_update.ensure_checkout(force=True, with_branch_heads=True)

  export_tarball(
      api,
      ['--remove-nonessential-files', 'chromium-%s' % version],
      'chromium-%s.tar.xz' % version,
      'chromium-%s.tar.xz' % version)

def GenTests(api):
  yield (
    api.test('basic') +
    api.properties.generic(version='38.0.2125.122') +
    api.platform('linux', 64)
  )
