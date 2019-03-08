# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions and constants related to build.git used by all modules."""


def poller(name):
  """Defines a gitiles poller."""
  luci.gitiles_poller(
      name = name,
      bucket = 'ci',
      repo = 'https://chromium.googlesource.com/chromium/tools/build',
  )


def recipe(name):
  """Defines a recipe hosted in the build.git recipe bundle."""
  luci.recipe(
      name = name,
      cipd_package = 'infra/recipe_bundles/chromium.googlesource.com/chromium/tools/build',
  )


build = struct(
    poller = poller,
    recipe = recipe,
)
