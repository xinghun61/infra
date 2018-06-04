# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property


DEPS = [
    'depot_tools/cipd',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/json',
    'recipe_engine/python',
    'recipe_engine/runtime',
    'recipe_engine/step',
]

PROPERTIES = {
  # TODO(tandrii): get rid of mastername once migrated to LUCI.
  'mastername': Property(default=None),
  'buildername': Property(),
  'buildnumber': Property(default=-1, kind=int),
}
