# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
  'depot_tools/tryserver',
  'infra_checkout',
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/runtime',
]

PROPERTIES = {
  'GOARCH': Property(
    default=None,
    kind=str,
    help="set GOARCH environment variable for go build+test"),
}

LUCI_GO_PATH_IN_INFRA = 'infra/go/src/go.chromium.org/luci'


def RunSteps(api, GOARCH):
  co = api.infra_checkout.checkout('luci_go', patch_root=LUCI_GO_PATH_IN_INFRA)
  is_presubmit = 'presubmit' in api.buildbucket.builder_id.builder.lower()
  if is_presubmit:
    co.commit_change()
  co.gclient_runhooks()

  env = {}
  if GOARCH is not None:
    env['GOARCH'] = GOARCH

  with api.context(env=env):
    co.ensure_go_env()
    if is_presubmit:
      with api.tryserver.set_failure_hash():
        co.run_presubmit_in_go_env()
    else:
      co.go_env_step('go', 'build', 'go.chromium.org/luci/...')
      co.go_env_step('go', 'test', 'go.chromium.org/luci/...')


def GenTests(api):
  yield (
    api.test('luci_go') +
    api.runtime(is_luci=True, is_experimental=False) +
    api.buildbucket.ci_build(
        'infra', 'ci', 'luci-gae-trusty-64',
        git_repo="https://chromium.googlesource.com/infra/luci/luci-go",
        revision='1'*40) +
    # Sadly, hacks in gclient required to patch non-main git repo in a solution
    # requires revsion as a property :(
    api.properties(revision='1'*40)
  )

  yield (
    api.test('presubmit_try_job') +
    api.runtime(is_luci=True, is_experimental=False) +
    api.buildbucket.try_build(
        'infra', 'try', 'Luci-go Presubmit', change_number=607472, patch_set=2,
    ) + api.step_data('presubmit', api.json.output([[]]))
  )

  yield (
    api.test('override_GOARCH') +
    api.platform('linux', 64) +
    api.runtime(is_luci=True, is_experimental=False) +
    api.buildbucket.try_build(
        'infra', 'try', 'luci-go-trusty-64', change_number=607472, patch_set=2,
    ) + api.properties(GOARCH='386')
  )
