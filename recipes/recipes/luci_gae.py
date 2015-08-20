# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'bot_update',
  'gclient',
  'path',
  'properties',
  'python',
  'tryserver',
]


def RunSteps(api):
  api.gclient.set_config('luci_gae')
  # patch_root must match the luci/gae repo, not infra checkout.
  for path in api.gclient.c.got_revision_mapping:
    if 'github.com/luci/gae' in path:
      patch_root = path
      break
  api.bot_update.ensure_checkout(force=True, patch_root=patch_root)
  api.gclient.runhooks()

  # This downloads the third parties, so that the next step doesn't have junk
  # output in it.
  api.python(
      'go third parties',
      api.path['checkout'].join('go', 'env.py'),
      ['go', 'version'])

  api.python(
      'go build',
      api.path['checkout'].join('go', 'env.py'),
      ['go', 'build', 'github.com/luci/gae/...'])

  api.python(
      'go test',
      api.path['checkout'].join('go', 'env.py'),
      ['go', 'test', 'github.com/luci/gae/...'])


def GenTests(api):
  yield (
    api.test('luci_gae') +
    api.properties.git_scheduled(
        buildername='luci-gae-linux64',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/external/github.com/luci/gae',
    )
  )
