# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Definitions of infra.git CI resources."""

load('//lib/build.star', 'build')
load('//lib/infra.star', 'infra')
load('//lib/recipes.star', 'recipes')


infra.console_view(name = 'infra', title = 'infra/infra repository console')
infra.cq_group(name = 'infra cq', tree_status_host = 'infra-status.appspot.com')


def ci_builder(name, os, cpu=None):
  infra.builder(
      name = name,
      bucket = 'ci',
      executable = infra.recipe('infra_continuous'),
      os = os,
      cpu = cpu,
      triggered_by = [infra.poller()],
  )
  luci.console_view_entry(
      builder = name,
      console_view = 'infra',
      category = infra.category_from_os(os, short=True),
  )


def try_builder(
      name,
      os,
      recipe=None,
      experiment_percentage=None,
      properties=None,
      cq=True
  ):
  infra.builder(
      name = name,
      bucket = 'try',
      executable = infra.recipe(recipe or 'infra_repo_trybot'),
      os = os,
      properties = properties,
  )
  if cq:
    luci.cq_tryjob_verifier(
        builder = name,
        cq_group = 'infra cq',
        experiment_percentage=experiment_percentage,
    )


# CI Linux.
ci_builder(name = 'infra-continuous-zesty-64', os = 'Ubuntu-17.04')
ci_builder(name = 'infra-continuous-yakkety-64', os = 'Ubuntu-16.10')
ci_builder(name = 'infra-continuous-xenial-64', os = 'Ubuntu-16.04')
ci_builder(name = 'infra-continuous-trusty-64', os = 'Ubuntu-14.04')

# CI OSX.
ci_builder(name = 'infra-continuous-mac-10.13-64', os = 'Mac-10.13')
ci_builder(name = 'infra-continuous-mac-10.12-64', os = 'Mac-10.12')

# CI Win.
ci_builder(name = 'infra-continuous-win7-64', os = 'Windows')
ci_builder(name = 'infra-continuous-win10-64', os = 'Windows-10')

# All trybots.
try_builder(name = 'infra-try-xenial-64', os = 'Ubuntu-16.04')
try_builder(name = 'infra-try-trusty-64', os = 'Ubuntu-14.04')
try_builder(name = 'infra-try-mac', os = 'Mac-10.13')
try_builder(name = 'infra-try-win', os = 'Windows')
try_builder(name = 'infra-try-frontend', os = 'Ubuntu-16.04', recipe = 'infra_frontend_tester')

# On demand (non-CQ) trybot for building docker images out of infra.git CLs.
try_builder(
    name = 'infra-try-images',
    os = 'Ubuntu-16.04',
    recipe = 'images_builder',
    cq = False,
    properties = {
        'mode': 'MODE_CI',
        'project': 'PROJECT_INFRA',
        'infra': 'dev',
        'manifests': ['infra/build/images/deterministic'],
    },
)

# Presubmit trybot.
build.presubmit(name = 'infra-try-presubmit', cq_group = 'infra cq', repo_name = 'infra')

# Recipes ecosystem.
recipes.simulation_tester(
    name = 'infra-continuous-recipes-tests',
    project_under_test = 'infra',
    triggered_by = infra.poller(),
    console_view = 'infra',
    console_category = 'misc',
)
