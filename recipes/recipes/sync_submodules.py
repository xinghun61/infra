# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'sync_submodules',
  'recipe_engine/properties',
]


DEFAULT_SOURCE_REPO = 'https://chromium.googlesource.com/chromium/src'


def RunSteps(api):
  source_repo = api.properties.get('source_repo', DEFAULT_SOURCE_REPO)
  dest_repo = api.properties.get('dest_repo', source_repo + '/codesearch')
  out_repo = api.properties.get('out_repo', None)

  extra_submodules = None
  if out_repo:
    extra_submodules = [('src/out', out_repo)]

  api.sync_submodules(source_repo, dest_repo, extra_submodules=extra_submodules)


def GenTests(api):
  yield api.test('basic') + api.properties(buildername='foo_builder')
  yield api.test('with_out_repo') + api.properties(
      buildername='foo_builder',
      out_repo='https://www.example.com')
