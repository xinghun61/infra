# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of depot_tools.git CI resources."""

load('//lib/infra.star', 'infra')
load('//lib/recipes.star', 'recipes')


REPO_URL = 'https://chromium.googlesource.com/chromium/tools/depot_tools'


luci.gitiles_poller(
    name = 'depot_tools-gitiles-trigger',
    bucket = 'ci',
    repo = REPO_URL,
)

infra.console_view(
    name = 'depot_tools',
    title = 'depot_tools repository console',
    repo = REPO_URL,
)


# Recipes ecosystem.
recipes.simulation_tester(
    name = 'depot_tools-recipes-tests',
    project_under_test = 'depot_tools',
    triggered_by = 'depot_tools-gitiles-trigger',
    console_view = 'depot_tools',
)
