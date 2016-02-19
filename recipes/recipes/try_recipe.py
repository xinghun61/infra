# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A recipe for actually running recipe on build/ repo patches as tryjobs.

Usage:
  $ # $EDITOR <YOUR_RECIPE>
  $ # hack, hack, commit.
  $ git cl upload
  $ git cl try -m tryserver.infra -b <BOT> -p try_recipe=<YOUR_RECIPE> \
        -p try_props=$(echo '{"abc":"cde"}' | python -c "import zlib, sys,
        base64; print base64.b64encode(zlib.compress(sys.stdin.read()))")

  You may repeat -b <BOT> for each bot you want.
  Available bots are currently on master.tryserver.infra.
"""

import base64
import json
import zlib


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


def decode(x):
  return json.loads(zlib.decompress(base64.b64decode(x)))


def encode(x):
  return base64.b64encode(zlib.compress(json.dumps(x), 9))


def RunSteps(api):
  """Check out itself, maybe apply patch, and then execute_inner real itself."""
  api.gclient.set_config('build')
  api.bot_update.ensure_checkout(force=True, patch_root='build')

  recipe = str(api.properties['try_recipe'])
  level = int(api.properties.get('try_level', '0'))
  # Escaping multiple layers of json is hell, so wrap them with base64.
  raw_properties = api.properties.get('try_props', encode({}))
  properties = decode(raw_properties)
  properties = dict((str(k), str(v)) for k, v in properties.iteritems())

  properties.setdefault('try_level', level + 1)
  for attr in ['buildername', 'mastername', 'buildnumber', 'slavename']:
    properties.setdefault(attr, api.properties.get(attr))

  step = api.step('properties (%d)' % level, cmd=None)
  step.presentation.logs['properties'] = (
      json.dumps(properties, sort_keys=True, indent=2)).splitlines()
  return api.python(
      name='%s run' % (recipe.replace('/', '.')),
      script=api.path['checkout'].join('scripts', 'tools',
                                       'annotee_indenter.py'),
      args=[
        '--base-level', str(level + 1),
        '--use-python-executable',
        '--',
        api.path['checkout'].join('scripts', 'slave', 'recipes.py'),
        'run',
        '--properties-file',
        api.json.input(properties),
        recipe,
      ],
      allow_subannotations=True,
  )


def GenTests(api):
  yield (
      api.test('default') +
      api.properties.tryserver(
          mastername='tryserver.infra',
          buildername='recipe_try',
          try_recipe='infra/build_repo_real_try',
          try_props=encode({
            'prop1': 'value1',
            'prop2': 'value2',
          })
      )
  )
  yield (
      api.test('recursion') +
      api.properties.tryserver(
          mastername='tryserver.infra',
          buildername='recipe_try',
          try_recipe='infra/try_other_recipe',
          try_level='1',
          try_props=encode({
            'try_recipe': 'infra/build_repo_real_try',
            'try_props': encode({
              'prop1': 'value1',
              'prop2': 'value2',
            }),
          }),
      )
  )
