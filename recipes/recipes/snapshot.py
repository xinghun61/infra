# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'recipe_engine/cipd',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
]


def RunSteps(api):
  packages_dir = api.path['cache'].join('packages')
  ensure_file = api.cipd.EnsureFile()
  ensure_file.add_package('infra/tools/luci/swarming/${platform}', 'latest')
  api.cipd.ensure(packages_dir, ensure_file)
  # TODO(smut): Query Swarming for MP VMs, then trigger snapshotting tasks.


def GenTests(api):
  yield (
    api.test('snapshot') +
    api.platform('linux', 64) +
    api.properties.git_scheduled(
        buildername='snapshot',
    )
  )
