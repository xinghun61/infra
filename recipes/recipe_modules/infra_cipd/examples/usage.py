# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json


DEPS = [
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/runtime',
  'recipe_engine/step',

  'infra_cipd',
]


def RunSteps(api):
  url = 'https://chromium.googlesource.com/infra/infra'
  rev = 'deadbeef' * 5
  # Assume path is where infra/infra is repo is checked out.
  path = api.path['builder_cache'].join('assume', 'infra')
  with api.infra_cipd.context(
      path_to_repo=path,
      goos=api.properties.get('goos'),
      goarch=api.properties.get('goarch')):
    api.infra_cipd.build()
    api.infra_cipd.test()
    if api.properties.get('buildnumber'):
      api.infra_cipd.upload(api.infra_cipd.tags(url, rev))


def GenTests(api):
  yield (
    api.test('luci-native') +
    api.properties(
      path_config='generic',
      buildername='native',
      buildnumber=5,
    ) +
    api.buildbucket.ci_build('infra-internal', 'ci', 'native') +
    api.runtime(is_luci=True, is_experimental=False))
  yield (
    api.test('luci-cross') +
    api.properties(
      path_config='generic',
      goos='linux',
      goarch='arm64',
      buildername='cross',
      buildnumber=5,
    ) +
    api.buildbucket.ci_build('infra-internal', 'ci', 'cross') +
    api.runtime(is_luci=True, is_experimental=False))
  yield (
    api.test('no-buildnumbers') +
    api.properties(
      path_config='generic',
      buildername='just-build-and-test',
    ) +
    api.buildbucket.ci_build('infra-internal', 'ci', 'just-build-and-test') +
    api.runtime(is_luci=True, is_experimental=False))
