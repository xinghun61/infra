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


LUCI_GO_ROOT = 'infra/go/src/github.com/luci/luci-go'


def RunSteps(api):
  api.gclient.set_config('luci_go')
  # patch_root must match the luci-go repo, not infra checkout.
  for path in api.gclient.c.got_revision_mapping:
    if 'luci-go' in path:
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
      ['go', 'build', 'github.com/luci/luci-go/...'])

  api.python(
      'go test',
      api.path['checkout'].join('go', 'env.py'),
      ['go', 'test', 'github.com/luci/luci-go/...'])


def GenTests(api):
  yield (
    api.test('luci_go') +
    api.properties.git_scheduled(
        buildername='luci-go-linux64',
        buildnumber=123,
        mastername='chromium.infra',
        repository='https://chromium.googlesource.com/external/github.com/luci/luci-go',
    )
  )
