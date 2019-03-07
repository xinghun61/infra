# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Support for defining builders that run PRESUBMIT.py checks."""

load('//lib/infra.star', 'infra')


def recipe():
  """Defines 'run_presubmit' recipe needed by all presubmit builders."""
  luci.recipe(
      name = 'run_presubmit',
      cipd_package = 'infra/recipe_bundles/chromium.googlesource.com/chromium/tools/build',
  )


def builder(
      *,

      name,
      cq_group,
      repo_name  # e.g. 'infra' or 'luci_py', as expected by the recipe
  ):
  """Defines a try builder that runs 'run_presubmit' recipe."""
  luci.builder(
      name = name,
      bucket = 'try',
      recipe = 'run_presubmit',
      properties = {'repo_name': repo_name, 'runhooks': True},
      service_account = infra.SERVICE_ACCOUNT_TRY,
      execution_timeout = 30 * time.minute,
      dimensions = {
          'os': 'Ubuntu-14.04',
          'cpu': 'x86-64',
          'pool': 'luci.flex.try',
      },
      swarming_tags = ['vpython:native-python-wrapper'],
  )
  luci.cq_tryjob_verifier(
      builder = name,
      cq_group = cq_group,
      disable_reuse = True,
  )


presubmit = struct(
    recipe = recipe,
    builder = builder,
)
