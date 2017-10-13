# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Pushes a trivial CL to Gerrit to verify git authentication works on LUCI."""


DEPS = [
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/step',
  'recipe_engine/time',
]


PLAYGROUND_REPO = 'https://chromium.googlesource.com/playground/access_test'


def RunSteps(api):
  root_dir = api.path['tmp_base'].join('repo')
  api.file.ensure_directory('make dir', root_dir)

  with api.context(cwd=root_dir):
    api.step('git clone', ['git', 'clone', PLAYGROUND_REPO, '.'])
    api.step('git checkout -b', ['git', 'checkout', '-b', 'cl'])
    api.file.write_text(
        'drop file', root_dir.join('time.txt'), str(api.time.time()))
    api.step('git add', ['git', 'add', 'time.txt'])
    api.step('git commit', ['git', 'commit', '-m', 'Test commit'])
    api.step(
        'push for review',
        ['git', 'push', 'origin', 'HEAD:refs/for/refs/heads/master'])


def GenTests(api):
  yield (
      api.test('linux') +
      api.platform.name('linux') +
      api.properties.generic(
          buildername='test_builder',
          mastername='test_master'))
