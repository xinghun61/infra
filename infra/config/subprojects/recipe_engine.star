# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of recipes-py.git (aka recipe_engine) CI resources."""

load('//lib/infra.star', 'infra')
load('//lib/presubmit.star', 'presubmit')
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

luci.cq_group(
    name = 'recipes-py cq',
    watch = cq.refset(repo = REPO_URL, refs = [r'refs/heads/.+']),
    retry_config = cq.RETRY_ALL_FAILURES,
)


# Presubmit trybots.
presubmit.builder(
    name = 'Recipes-py Presubmit',
    cq_group = 'recipes-py cq',
    repo_name = 'recipes_py',
)
presubmit.builder(
    name = 'Recipes-py Windows Presubmit',
    cq_group = 'recipes-py cq',
    repo_name = 'recipes_py',
    os = 'Windows-10',
    experiment_percentage = 100,
)


# Recipes ecosystem.
recipes.simulation_tester(
    name = 'recipe_engine-recipes-tests',
    project_under_test = 'recipe_engine',
    triggered_by = 'recipe_engine-gitiles-trigger',
    console_view = 'recipes-py',
)
