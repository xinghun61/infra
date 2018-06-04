# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json


DEPS = [
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
    api.infra_cipd.test(skip_if_cross_compiling=True)
    if api.properties.get('buildnumber'):
      api.infra_cipd.upload(api.infra_cipd.tags(url, rev))


def GenTests(api):
  # TODO(tandrii): move this to buildbucket's recipe module.
  buildbucket_prop_value = json.dumps({
    "build": {
      "bucket": "luci.infra-internal.ci",
      "created_by": "user:luci-scheduler@appspot.gserviceaccount.com",
      "created_ts": 1527292217677440,
      "id": "8945511751514863184",
      "project": "infra-internal",
      "tags": [
        "builder:infra-internal-continuous-trusty-32",
        ("buildset:commit/gitiles/chrome-internal.googlesource.com/" +
          "infra/infra_internal/" +
          "+/2d72510e447ab60a9728aeea2362d8be2cbd7789"),
        "gitiles_ref:refs/heads/master",
        "scheduler_invocation_id:9110941813804031728",
        "user_agent:luci-scheduler",
      ],
    },
    "hostname": "cr-buildbucket.appspot.com"
  })
  yield (
    api.test('luci-native') +
    api.properties(
      path_config='generic',
      buildername='native',
      buildnumber=5,
      buildbucket=buildbucket_prop_value,
    ) +
    api.runtime(is_luci=True, is_experimental=False))
  yield (
    api.test('luci-cross') +
    api.properties(
      path_config='generic',
      goos='linux',
      goarch='arm64',
      buildername='cross',
      buildnumber=5,
      buildbucket=buildbucket_prop_value,
    ) +
    api.runtime(is_luci=True, is_experimental=False))
  yield (
    api.test('buildbot-legacy') +
    api.properties(
      path_config='generic',
      buildername='buildbot-native',
      buildnumber=5,
      mastername='chromium.infra',
    ) +
    api.runtime(is_luci=False, is_experimental=False))
  yield (
    api.test('no-buildnumbers') +
    api.properties(
      path_config='generic',
      buildername='just-build-and-test',
      buildbucket=buildbucket_prop_value,
    ) +
    api.runtime(is_luci=True, is_experimental=False))
