# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'depot_tools/tryserver',
    'infra_checkout',
    'recipe_engine/buildbucket',
    'recipe_engine/platform',
    'recipe_engine/raw_io',
    'recipe_engine/runtime',
]

def RunSteps(api):
  co = api.infra_checkout.checkout(
      gclient_config_name='infra', patch_root='infra')
  co.commit_change()
  co.get_changed_files()
  if api.platform.is_linux:
    with api.tryserver.set_failure_hash():
      co.run_presubmit_in_go_env()


def GenTests(api):
  def diff(*files):
    return api.step_data(
        'get change list', api.raw_io.stream_output('\n'.join(files)))

  for plat in ('linux', 'mac', 'win'):
    yield (
        api.test(plat) +
        api.platform(plat, 64) +
        api.runtime(is_luci=True, is_experimental=False) +
        api.buildbucket.try_build(
            project='infra',
            bucket='try',
            builder='presubmit',
            git_repo='https://chromium.googlesource.com/infra/infra',
        ) +
        # Simulate too many files on Mac.
        diff(*['file_%d' % i for i in xrange(1000 if plat == 'mac' else 2)])
    )
