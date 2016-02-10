# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A recipe for actually running recipe on build/ repo patches as tryjobs.

The idea is to actually execute some common recipe things so as to prevent
major outages.
"""

import json

DEPS = [
  'depot_tools/bot_update',
  'file',
  'depot_tools/gclient',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'depot_tools/tryserver'
]


def RunSteps(api):
  if api.properties.get('actual_run'):
    inner(api)
  else:
    outer(api)


def execute_inner(api, name, recipe, **properties):
  for attr in ['buildername', 'mastername', 'buildnumber', 'slavename']:
    properties.setdefault(attr, api.properties.get(attr))
  properties['actual_run'] = 'True'
  return api.python(
      name=name,
      script=api.path['checkout'].join('scripts', 'tools', 'run_recipe.py'),
      args=[
        recipe,
        '--master-overrides-slave',
        '--properties-file',
        api.json.input(properties),
      ],
      allow_subannotations=True,
  )


def outer(api):
  """Check out itself, maybe apply patch, and then execute_inner real itself."""
  api.gclient.set_config('build')
  api.bot_update.ensure_checkout(force=True, patch_root='build')

  recipe = api.properties['experimental_try_recipe']
  properties = api.properties.get('experimental_try_recipe_properties', '{}')
  properties = json.loads(properties)

  step = execute_inner(api, 'YOUR RECIPE STARTS BELOW. YELLOW FOR VISIBILITY',
                       recipe, **properties)
  step.presentation.status = api.step.WARNING
  step = api.step('YOUR RECIPE ENDED ABOVE. YELLOW FOR VISIBILITY', cmd=None)
  step.presentation.status = api.step.WARNING


def inner(api):
  """Actually performs basic tasks common to most recipes."""
  api.gclient.set_config('build')
  api.bot_update.ensure_checkout(force=True, patch_root='build')


def GenTests(api):
  yield (
      api.test('outer') +
      api.properties.tryserver(
          mastername='tryserver.infra',
          buildername='recipe_try',
          experimental_try_recipe='infra/build_repo_real_try',
          experimental_try_recipe_properties=json.dumps({
            'prop1': 'value1',
            'prop2': 'value2',
          })
      )
  )
  yield (
      api.test('inner') +
      api.properties.generic(
          mastername='tryserver.infra',
          buildername='build_repo_real_try',
          actual_run='True',
          prop1='value1',
          prop2='value2',
      )
  )
