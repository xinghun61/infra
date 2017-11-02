# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Pushes a trivial CL to Gerrit to verify git authentication works on LUCI."""


DEPS = [
  'depot_tools/gsutil',
  'recipe_engine/file',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/step',
  'recipe_engine/time',
]


def RunSteps(api):
  root_dir = api.path['tmp_base']
  name = 'access_test'

  api.file.write_text('write %s' % name, root_dir.join(name),
                      str(api.time.time()))
  api.gsutil.upload(root_dir.join(name), 'luci-playground', name)


def GenTests(api):
  yield (
      api.test('linux') +
      api.platform.name('linux') +
      api.properties.generic(
          buildername='test_builder',
          mastername='test_master'))
