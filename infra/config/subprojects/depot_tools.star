# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of depot_tools.git CI resources."""

load('//lib/infra.star', 'infra')
load('//lib/presubmit.star', 'presubmit')
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

luci.cq_group(
    name = 'depot_tools cq',
    watch = cq.refset(repo = REPO_URL, refs = [r'refs/heads/.+']),
    retry_config = cq.RETRY_ALL_FAILURES,
)


# Presubmit trybots.
presubmit.builder(
    name = 'Depot Tools Presubmit',
    cq_group = 'depot_tools cq',
    repo_name = 'depot_tools',
)


# Recipes ecosystem.
recipes.simulation_tester(
    name = 'depot_tools-recipes-tests',
    project_under_test = 'depot_tools',
    triggered_by = 'depot_tools-gitiles-trigger',
    console_view = 'depot_tools',
)


# Recipe rolls from Depot Tools.
recipes.roll_trybots(
    upstream = 'depot_tools',
    downstream = [
        'build',
        'infra',
        'skia',
        'skiabuildbot',
    ],
    cq_group = 'depot_tools cq',
)


# External testers (defined in another project) for recipe rolls.
luci.cq_tryjob_verifier(
    builder = 'external/infra-internal/try/build_limited Roll Tester (depot_tools)',
    cq_group = 'depot_tools cq',
)
luci.cq_tryjob_verifier(
    builder = 'external/infra-internal/try/release_scripts Roll Tester (depot_tools)',
    cq_group = 'depot_tools cq',
)


# CI builder that uploads depot_tools.zip to Google Storage.
#
# TODO(crbug.com/940149): Move to the prod pool.
infra.recipe(name = 'depot_tools_builder')
luci.builder(
    name = 'depot_tools zip uploader',
    bucket = 'ci',
    recipe = 'depot_tools_builder',
    dimensions = {
        'cpu': 'x86-64',
        'os': 'Ubuntu-14.04',
        'pool': 'luci.flex.ci',
    },
    service_account = 'infra-ci-depot-tools-uploader@chops-service-accounts.iam.gserviceaccount.com',
    execution_timeout = 30 * time.minute,
    swarming_tags = ['vpython:native-python-wrapper'],
    build_numbers = True,
    triggered_by = ['depot_tools-gitiles-trigger'],
)
luci.console_view_entry(
    builder = 'depot_tools zip uploader',
    console_view = 'depot_tools',
)
