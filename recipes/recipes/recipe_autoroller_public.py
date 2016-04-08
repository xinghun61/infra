# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Rolls recipes.cfg dependencies for public projects."""

DEPS = [
  'recipe_autoroller',
  'recipe_engine/properties',
]

from recipe_engine import recipe_api


# Toposorted for best results.
# TODO(phajdan.jr): get the list of public projects from luci-config.
PROJECTS = [
  'depot_tools',
  'build',
]


PROPERTIES = {
  'projects': recipe_api.Property(default=PROJECTS),
}


def RunSteps(api, projects):
  api.recipe_autoroller.prepare_checkout()
  api.recipe_autoroller.roll_projects(projects)


def GenTests(api):
  yield (
      api.test('basic') +
      api.properties(projects=['build']) +
      api.recipe_autoroller.roll_data('build')
  )

  yield (
      api.test('nontrivial') +
      api.properties(projects=['build']) +
      api.recipe_autoroller.roll_data('build', trivial=False)
  )

  yield (
      api.test('empty') +
      api.properties(projects=['build']) +
      api.recipe_autoroller.roll_data('build', empty=True)
  )

  yield (
      api.test('failure') +
      api.properties(projects=['build']) +
      api.recipe_autoroller.roll_data('build', success=False)
  )
