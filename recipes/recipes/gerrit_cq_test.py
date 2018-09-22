# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/buildbucket',
  'recipe_engine/properties',
  'recipe_engine/step',
]

REPO = 'https://chromium.googlesource.com/playground/gerrit-cq/normal'


def RunSteps(api):
  api.gclient.set_config('gerrit_test_cq_normal')
  api.bot_update.ensure_checkout(patch=True)
  if 'experimental' in api.buildbucket.builder_name:
    api.step('fail', ['unknown-command', '1'], infra_step=True)


def GenTests(api):
  yield (
    api.test('try') +
    api.buildbucket.try_build(
        project='playground',
        builder='linux',
        git_repo='https://chromium.googlesource.com/playground/gerrit-cq/normal'
    )
  )
  yield (
    api.test('try-experimental') +
    api.buildbucket.try_build(
        project='playground',
        builder='experimental',
        git_repo='https://chromium.googlesource.com/playground/gerrit-cq/normal'
    )
  )
