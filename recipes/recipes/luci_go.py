# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/presubmit',
  'depot_tools/tryserver',
  'infra_checkout',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]

PROPERTIES = {
  'presubmit': Property(
    default=False,
    kind=bool,
    help=(
      "if set, will run presubmit for the luci-go repo, otherwise runs tests."
    )),

  'GOARCH': Property(
    default=None,
    kind=str,
    help="set GOARCH environment variable for go build+test"),
}

LUCI_GO_PATH_IN_INFRA = 'infra/go/src/go.chromium.org/luci'


def RunSteps(api, presubmit, GOARCH):
  co = api.infra_checkout.checkout('luci_go', patch_root=LUCI_GO_PATH_IN_INFRA)
  if presubmit:
    co.commit_change()
  co.gclient_runhooks()

  env = {}
  if GOARCH is not None:
    env['GOARCH'] = GOARCH

  with api.context(env=env):
    co.ensure_go_env()
    if presubmit:
      with api.tryserver.set_failure_hash():
        co.run_presubmit_in_go_env()
    else:
      co.go_env_step('go', 'build', 'go.chromium.org/luci/...')
      co.go_env_step('go', 'test', 'go.chromium.org/luci/...')


def GenTests(api):
  yield (
    api.test('luci_go') +
    api.properties.git_scheduled(
        path_config='generic',
        buildername='luci-go-linux64',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/infra/luci/luci-go',
    )
  )

  yield (
    api.test('presubmit_try_job') +
    api.properties(
        buildername='Luci-go Presubmit',
        mastername='tryserver.infra',
        patch_gerrit_url='https://chromium-review.googlesource.com',
        patch_issue=607472,
        patch_set=2,
        path_config='generic',
        presubmit=True,
    ) + api.step_data('presubmit', api.json.output([[]]))
  )

  yield (
    api.test('override_GOARCH') +
    api.platform('linux', 64) +
    api.properties.tryserver(
        path_config='generic',
        mastername='tryserver.infra',
        buildername='Luci-go 32-on-64 Tests',
        GOARCH='386',
    )
  )
