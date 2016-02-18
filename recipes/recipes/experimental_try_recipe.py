# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A recipe for actually running recipe on build/ repo patches as tryjobs.

The idea is to actually execute some common recipe things so as to prevent
major outages.
"""

import base64
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


def execute_recipe(api, name, recipe, level, **properties):
  properties.setdefault('exp_try_level', level + 1)
  for attr in ['buildername', 'mastername', 'buildnumber', 'slavename']:
    properties.setdefault(attr, api.properties.get(attr))
  return api.python(
      name=name,
      script=api.path['checkout'].join('scripts', 'slave', 'recipes.py'),
      args=[
        'run',
        '--properties-file',
        api.json.input(properties),
        recipe,
      ],
      allow_subannotations=True,
  )


def RunSteps(api):
  """Check out itself, maybe apply patch, and then execute_inner real itself."""
  api.gclient.set_config('build')
  api.bot_update.ensure_checkout(force=True, patch_root='build')

  recipe = api.properties['exp_try_recipe']
  level = int(api.properties.get('exp_try_level', '0'))
  # Escaping multiple layers of json is hell, so wrap them with base64.
  b64properties = api.properties.get('exp_try_props', base64.b64encode('{}'))
  properties = json.loads(base64.b64decode(b64properties))
  properties = dict((str(k), str(v)) for k, v in properties.iteritems())

  step = api.step('YOUR RECIPE STARTS BELOW (%d)' % level, cmd=None)
  step.presentation.logs['properties'] = [
      '%s: %s' % (k, v) for k, v in sorted(properties.iteritems())]
  step.presentation.status = api.step.WARNING
  try:
    execute_recipe(api, '%s run' % (recipe.replace('/', '.')),
                   recipe, level, **properties)
  finally:
    step = api.step('YOUR RECIPE ENDED ABOVE (%d)' % level, cmd=None)
    step.presentation.status = api.step.WARNING


def GenTests(api):
  yield (
      api.test('default') +
      api.properties.tryserver(
          mastername='tryserver.infra',
          buildername='recipe_try',
          exp_try_recipe='infra/build_repo_real_try',
          exp_try_props=base64.b64encode(json.dumps({
            'prop1': 'value1',
            'prop2': 'value2',
          }))
      )
  )
  yield (
      api.test('level-5') +
      api.properties.tryserver(
          mastername='tryserver.infra',
          buildername='recipe_try',
          exp_try_recipe='infra/build_repo_real_try',
          exp_try_level='5',
          exp_try_props=base64.b64encode(json.dumps({
            'prop1': 'value1',
            'prop2': 'value2',
          }))
      )
  )
