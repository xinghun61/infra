# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/buildbucket',
  'recipe_engine/properties',
]


def RunSteps(api):
  api.gclient.set_config('luci_py')
  api.bot_update.ensure_checkout()
  # TODO(tandrii): trigger tests without PRESUBMIT.py .


def GenTests(api):
  yield (
      api.test('ci') +
      api.buildbucket.ci_build(
          'infra', 'ci', 'Luci-py linux-64',
          git_repo='https://chromium.googlesource.com/infra/luci/luci-py',
      ) +
      api.properties(revision='1'*40)
  )

  yield (
      api.test('try') +
      api.buildbucket.try_build(
          'infra', 'try', 'Luci-py Presubmit',
          git_repo='https://chromium.googlesource.com/infra/luci/luci-py',
      )
  )
