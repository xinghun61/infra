# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A recipe for actually running recipe on build/ repo patches as tryjobs.

The idea is to actually execute some common recipe things so as to prevent
major outages.
"""

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/tryserver',
  'build/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
]


def RunSteps(api):
  if api.properties.get('actual_run'):
    inner(api)
  else:
    outer(api)


def execute_inner(api, name, **properties):
  for attr in ['buildername', 'mastername', 'buildnumber', 'slavename']:
    properties.setdefault(attr, api.properties.get(attr))
  properties['actual_run'] = 'True'
  return api.python(
      name=name,
      script=api.path['checkout'].join('scripts', 'slave', 'recipes.py'),
      args=[
        'run',
        '--properties-file',
        api.json.input(properties),
        'infra/build_repo_real_try',
      ],
      allow_subannotations=True,
  )


def outer(api):
  """Check out itself, maybe apply patch, and then execute_inner real itself."""
  api.gclient.set_config('build')
  api.bot_update.ensure_checkout(patch_root='build')

  execute_inner(api, 'ci actual execute_inner')

  execute_inner(api, 'try patch from Rietveld',
    # https://codereview.chromium.org/1662543002/
    issue='1662543002',
    patch_storage='rietveld',
    patch_project='build',
    patchset='1',
    reason='CQ',
    rietveld='https://codereview.chromium.org'
  )
  # TODO(tandrii): same for Gerrit.


def inner(api):
  """Actually performs basic tasks common to most recipes."""
  api.gclient.set_config('build')
  api.bot_update.ensure_checkout(patch_root='build')

  api.git.checkout(
      url='https://chromium.googlesource.com/chromium/tools/build',
      ref='master',
      dir_path=api.path['build'].join('clone'))


def GenTests(api):
  yield (
      api.test('ok-outer') +
      api.properties.generic(
          mastername='chromium.infra',
          buildername='build_repo_real',
      )
  )
  yield (
      api.test('ok-outer-try') +
      api.properties.tryserver(
          mastername='tryserver.infra',
          buildername='build_repo_real',
      )
  )
  yield (
      api.test('ok-inner') +
      api.properties.generic(
          mastername='chromium.infra',
          buildername='build_repo_real',
          actual_run='True',
      )
  )
  yield (
      api.test('ok-inner-win') +
      api.platform('win', 64) +
      api.properties.generic(
          mastername='chromium.infra',
          buildername='build_repo_real',
          actual_run='True',
      )
  )
  yield (
      api.test('ok-inner-try-rietveld') +
      api.properties.tryserver(
          mastername='tryserver.infra',
          buildername='build_repo_real',
          actual_run='True',
      )
  )
