# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe for Tricium that outputs no results.

This is intended as a simple test for recipe-based analyzers.
It doesn't do anything.
"""


DEPS = [
    'recipe_engine/properties',
    'recipe_engine/tricium',
]

def RunSteps(api):
  # Write empty results.
  api.tricium.write_comments([])


def GenTests(api):
  # There are no required properties.
  yield api.test('default') + api.properties()
