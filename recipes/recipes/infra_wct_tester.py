# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/cipd',
  'recipe_engine/context',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/step',
]

def RunSteps(api):
  project_name = 'infra'

  api.gclient.set_config(project_name)
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()

  packages_dir = api.path['start_dir'].join('packages')
  ensure_file = api.cipd.EnsureFile()
  ensure_file.add_package('infra/nodejs/nodejs/${platform}',
      'node_version:8.9.4')
  api.cipd.ensure(packages_dir, ensure_file)

  node_path = api.path['start_dir'].join('packages', 'bin')
  env = {
      'PATH': api.path.pathsep.join([str(node_path), '%(PATH)s'])
  }

  cwd = api.path['checkout'].join('crdx', 'chopsui')
  with api.context(env=env, cwd=cwd):
    api.step('chopsui npm install', ['npm', 'install'])
    api.step('chopsui bower install', ['npx', 'bower', 'install'])
    api.step('chopsui run-wct', ['npx', 'run-wct', '--prefix', 'test',
        '--dep', 'bower_components'])
    api.step('chopsui generate js coverage report', ['npx', 'nyc', 'report'])

  cwd = api.path['checkout'].join('appengine', 'monorail')
  with api.context(env=env, cwd=cwd):
    api.step('monorail npm install', ['npm', 'install'])
    api.step('monorail bower install', ['npx', 'bower', 'install'])
    api.step('monorail run-wct', ['npx', 'run-wct'])
    api.step('monorail generate js coverage report', ['npx', 'nyc', 'report'])

  cwd = api.path['checkout'].join('go', 'src', 'infra', 'appengine',
      'sheriff-o-matic', 'frontend')
  with api.context(env=env, cwd=cwd):
    api.step('sheriff-o-matic npm install', ['npm', 'install'])
    api.step('sheriff-o-matic bower install', ['npx', 'bower', 'install'])
    api.step('sheriff-o-matic run-wct', ['npx', 'run-wct'])
    api.step('sheriff-o-matic generate js coverage report',
        ['npx', 'nyc', 'report'])

def GenTests(api):
  yield api.test('basic')
  yield api.test('not-linux') + api.platform('win', 32)
  yield api.test('has package.json') + api.path.exists(
      api.path['checkout'].join('appengine', 'monorail', 'package.json'))
