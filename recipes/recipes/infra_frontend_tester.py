# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'infra_checkout',
  'recipe_engine/buildbucket',
  'recipe_engine/cipd',
  'recipe_engine/context',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/step',
]

def RunSteps(api):
  assert api.platform.is_linux, 'Unsupported platform, only Linux is supported.'
  cl = api.buildbucket.build.input.gerrit_changes[0]
  project_name = cl.project
  assert project_name in ('infra/infra', 'infra/infra_internal'), (
      'unknown project: "%s"' % project_name)
  patch_root = project_name.split('/')[-1]
  internal = (patch_root == 'infra_internal')
  api.gclient.set_config(patch_root)
  api.bot_update.ensure_checkout(patch_root=patch_root)
  api.gclient.runhooks()

  packages_dir = api.path['start_dir'].join('packages')
  ensure_file = api.cipd.EnsureFile()
  ensure_file.add_package('infra/nodejs/nodejs/${platform}',
      'node_version:10.15.3')
  api.cipd.ensure(packages_dir, ensure_file)

  node_path = api.path['start_dir'].join('packages', 'bin')
  env = {
      'PATH': api.path.pathsep.join([str(node_path), '%(PATH)s'])
  }
  if internal:
    RunInfraInternalFrontendTests(api, env)
  else:
    RunInfraFrontendTests(api, env)

def RunInfraInternalFrontendTests(api, env):
  cwd = api.path['checkout'].join('appengine', 'chromiumdash')
  with api.context(env=env, cwd=cwd):
    api.step('chromiumdash npm install', ['npm', 'ci'])
    api.step('chromiumdash bower install', ['npx', 'bower', 'install'])
    api.step(
        'chromiumdash run-wct', ['npx', 'run-wct', '--dep', 'third_party'])
    api.step(
        'chromiumdash generate js coverage report', ['npx', 'nyc', 'report'])

def RunInfraFrontendTests(api, env):
  cwd = api.path['checkout'].join('appengine', 'findit')
  with api.context(env=env, cwd=cwd):
    api.step('findit npm install', ['npm', 'ci'])
    api.step('findit run-wct', ['npx', 'run-wct', '--base', 'ui/',
        '--dep', 'third_party'])
    api.step('findit generate js coverage report', ['npx', 'nyc', 'report'])

  cwd = api.path['checkout'].join('crdx', 'chopsui')
  with api.context(env=env, cwd=cwd):
    api.step('chopsui npm install', ['npm', 'ci'])
    api.step('chopsui bower install', ['npx', 'bower', 'install'])
    api.step('chopsui run-wct', ['npx', 'run-wct', '--prefix', 'test',
        '--dep', 'bower_components'])
    api.step('chopsui generate js coverage report', ['npx', 'nyc', 'report'])

  cwd = api.path['checkout'].join('appengine', 'monorail')
  RunFrontendTests(api, env, cwd, 'monorail')

  cwd = api.path['checkout'].join('go', 'src', 'infra', 'appengine',
                                  'dashboard', 'frontend')
  RunFrontendTests(api, env, cwd, 'chopsdash')

  cwd = api.path['checkout'].join('go', 'src', 'infra', 'appengine',
      'sheriff-o-matic', 'frontend')
  with api.context(env=env, cwd=cwd):
    api.step('sheriff-o-matic npm install', ['npm', 'ci'])
    api.step('sheriff-o-matic bower install', ['npx', 'bower', 'install'])
    api.step('sheriff-o-matic run-wct', ['npx', 'run-wct'])
    api.step('sheriff-o-matic generate js coverage report',
        ['npx', 'nyc', 'report'])


def RunFrontendTests(api, env, cwd, app_name):
  with api.context(env=env, cwd=cwd):
    api.step(('%s npm install' % app_name), ['npm', 'ci'])
    api.step(('%s test' % app_name), ['npm', 'run', 'test'])


def GenTests(api):
  yield (
      api.test('basic') +
      api.buildbucket.try_build(project='infra/infra'))
  yield (
      api.test('basic-internal') +
      api.buildbucket.try_build(project='infra/infra_internal'))
