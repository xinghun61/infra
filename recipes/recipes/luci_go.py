# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'bot_update',
  'gclient',
  'path',
  'properties',
  'python',
]


def GenSteps(api):
  api.gclient.set_config('luci_go')
  api.bot_update.ensure_checkout(force=True)
  api.gclient.runhooks()
  api.python(
      'go build',
      api.path['checkout'].join('go', 'env.py'),
      ['go', 'build', 'github.com/luci/luci-go/cmd/...'])
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
    ))
