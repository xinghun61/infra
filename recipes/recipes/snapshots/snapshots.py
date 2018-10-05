# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'recipe_engine/buildbucket',
  'recipe_engine/cipd',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/step',
]


def RunSteps(api):
  packages_dir = api.path['start_dir'].join('packages')
  ensure_file = api.cipd.EnsureFile()
  ensure_file.add_package(
      'infra/machine-provider/snapshot/gce/${platform}', 'canary')
  api.cipd.ensure(packages_dir, ensure_file)

  snapshot = packages_dir.join('snapshot')
  api.step('snapshot', [snapshot, '-help'])
  # TODO(smut): Take the disk snapshot.


def GenTests(api):
  yield (
    api.test('snapshot') +
    api.platform('linux', 64) +
    api.buildbucket.ci_build()
  )
