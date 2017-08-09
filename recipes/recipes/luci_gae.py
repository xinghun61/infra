# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/presubmit',
  'depot_tools/tryserver',
  'infra_checkout',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]

LUCI_GAE_PATH_IN_INFRA = 'infra/go/src/go.chromium.org/gae'


def RunSteps(api):
  co = api.infra_checkout.checkout('luci_gae',
                                   patch_root=LUCI_GAE_PATH_IN_INFRA)
  is_presubmit = 'presubmit' in api.properties.get('buildername', '').lower()
  if is_presubmit:
    co.commit_change()
  co.gclient_runhooks()

  co.ensure_go_env()
  if is_presubmit:
    with api.tryserver.set_failure_hash():
      co.run_presubmit_in_go_env()
  else:
    co.go_env_step('go', 'build', 'go.chromium.org/gae/...')
    co.go_env_step('go', 'test', 'go.chromium.org/gae/...')


def GenTests(api):
  yield (
    api.test('luci_gae') +
    api.properties.git_scheduled(
        path_config='kitchen',
        buildername='luci-gae-linux64',
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/luci/gae',
    )
  )
  yield (
    api.test('presubmit_try_job') +
    api.properties(
        buildername='Luci-GAE Presubmit',
        mastername='tryserver.infra',
        patch_gerrit_url='https://chromium-review.googlesource.com',
        patch_issue=607472,
        patch_set=2,
        path_config='kitchen',
    ) + api.step_data('presubmit', api.json.output([[]]))
  )
