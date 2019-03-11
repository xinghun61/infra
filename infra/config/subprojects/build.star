# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of build.git CI resources."""

load('//lib/infra.star', 'infra')
load('//lib/recipes.star', 'recipes')


REPO_URL = 'https://chromium.googlesource.com/chromium/tools/build'


infra.console_view(
    name = 'build',
    title = 'build repository console',
    repo = REPO_URL,
)


# Recipes ecosystem.
recipes.simulation_tester(
    name = 'build-recipes-tests',
    project_under_test = 'build',
    triggered_by = 'build-gitiles-trigger',
    console_view = 'build',
)
