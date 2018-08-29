# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  "recipe_engine/path",

  "third_party_packages_ng",
]

def RunSteps(api):
  builder = api.path['cache'].join('builder')

  # do a checkout in `builder`

  package_names = api.third_party_packages_ng.load_packages_from_path(
    builder.join('package_repo'))
  api.third_party_packages_ng.ensure_uploaded([
    (name, 'latest') for name in package_names
  ])

def GenTests(api):
  yield api.test('basic')
