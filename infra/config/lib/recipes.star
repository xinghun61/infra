# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions and constants related to recipes ecosystem support."""

load('//lib/infra.star', 'infra')


def _recipes():
  """Defines all recipes used by this module."""
  infra.recipe(name = 'recipe_simulation')


def simulation_tester(
      name,
      project_under_test,
      triggered_by,
      console_view=None,
      console_category=None,
  ):
  """Defines a CI builder that runs recipe simulation tests."""
  luci.builder(
      name = name,
      bucket = 'ci',
      recipe = 'recipe_simulation',
      properties = {'project_under_test': project_under_test},
      dimensions = {
          'os': 'Ubuntu-14.04',
          'cpu': 'x86-64',
          'pool': 'luci.flex.ci',
      },
      service_account = infra.SERVICE_ACCOUNT_CI,
      build_numbers = True,
      execution_timeout = 30 * time.minute,
      swarming_tags = ['vpython:native-python-wrapper'],
      triggered_by = [triggered_by],
  )
  if console_view:
    luci.console_view_entry(
        builder = name,
        console_view = console_view,
        category = console_category,
    )


recipes = struct(
    recipes = _recipes,
    simulation_tester = simulation_tester,
)
