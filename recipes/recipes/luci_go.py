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

LUCI_GO_PATH_IN_INFRA = 'infra/go/src/github.com/luci/luci-go'
# NAMED_CACHE shared across various builders that rely on infra's Go env.
NAMED_CACHE = 'infra_gclient_with_go'


def _run_presubmit(api, co):
  got_revision_properties = api.bot_update.get_project_revision_properties(
      LUCI_GO_PATH_IN_INFRA)
  upstream = co.bot_update_step.json.output['properties'].get(
      got_revision_properties[0])
  # The presubmit must be run with proper Go environment.
  # infra/go/env.py takes care of this.
  presubmit_cmd = [
    'python',  # env.py will replace with this its sys.executable.
    api.presubmit.presubmit_support_path,
    '--root', co.patch_root_path,
    '--commit',
    '--verbose', '--verbose',
    '--issue', api.properties['issue'],
    '--patchset', api.properties['patchset'],
    '--skip_canned', 'CheckRietveldTryJobExecution',
    '--skip_canned', 'CheckTreeIsOpen',
    '--skip_canned', 'CheckBuildbotPendingBuilds',
    '--rietveld_url', api.properties['rietveld'],
    '--rietveld_fetch',
    '--upstream', upstream,
    '--rietveld_email', ''
  ]
  with api.context(env={'PRESUBMIT_BUILDER': '1'}):
    co.go_env_step(*presubmit_cmd, name='presubmit')


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
        _run_presubmit(api, co)
    else:
      co.go_env_step('go', 'build', 'github.com/luci/luci-go/...')
      co.go_env_step('go', 'test', 'github.com/luci/luci-go/...')


def GenTests(api):
  yield (
    api.test('luci_go') +
    api.properties.git_scheduled(
        path_config='generic',
        buildername='luci-go-linux64',
        buildnumber=123,
        mastername='chromium.infra',
        repository=('https://chromium.googlesource.com/external/github.com/'
                    'luci/luci-go'),
    )
  )

  yield (
    api.test('presubmit_try_job') +
    api.properties.tryserver(
        path_config='generic',
        mastername='tryserver.infra',
        buildername='Luci-go Presubmit',
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
