# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe for Tricium that outputs no results.

This is intended to be used as the default recipe for the
tricium builder, which shouldn't actually be used in runs
triggered by Tricium.
"""

DEPS = [
    'recipe_engine/properties',
    'recipe_engine/tricium',
]

from recipe_engine.config import List
from recipe_engine.recipe_api import Property


def RunSteps(api):
  # Write empty results.
  api.tricium.write_comments(dump=True)


def GenTests(api):

  yield (api.test('default') + api.properties(
      repository='https://chromium.googlesource.com/infra/infra',
      ref='ref/changes/99/123499/5',
      files=[
        {'path': 'path/to/file'},
        {'path': 'other/path/to/file'},
      ]))
