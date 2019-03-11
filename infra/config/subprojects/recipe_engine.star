# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of recipes-py.git (aka recipe_engine) CI resources."""

load('//lib/infra.star', 'infra')
load('//lib/recipes.star', 'recipes')


REPO_URL = 'https://chromium.googlesource.com/infra/luci/recipes-py'


luci.gitiles_poller(
    name = 'recipe_engine-gitiles-trigger',
    bucket = 'ci',
    repo = REPO_URL,
)

infra.console_view(
    name = 'recipes-py',
    title = 'recipes-py repository console',
    repo = REPO_URL,
)


# Recipes ecosystem.
recipes.simulation_tester(
    name = 'recipe_engine-recipes-tests',
    project_under_test = 'recipe_engine',
    triggered_by = 'recipe_engine-gitiles-trigger',
    console_view = 'recipes-py',
)
