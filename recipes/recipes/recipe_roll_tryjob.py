# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property, defer_results


DEPS = [
  'build/luci_config',
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/tryserver',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
]


PROPERTIES = {
  'upstream_project': Property(
      kind=str,
      help='Project to patch'),

  'downstream_project': Property(
      kind=str,
      help=('Project that includes |upstream_project| in recipes.cfg to be '
            'tested with upstream patch')),
}


def _get_recipes_path(api, recipes_cfg_path):
  current_cfg = api.json.read(
    'read recipes.cfg',
    recipes_cfg_path, step_test_data=lambda: api.json.test_api.output({}))
  return current_cfg.json.output.get('recipes_path', '')


def _checkout_project(api, workdir, project, project_config, patch):
  api.file.ensure_directory('%s checkout' % project, workdir)

  gclient_config = api.gclient.make_config()
  s = gclient_config.solutions.add()
  s.name = project
  s.url = project_config['repo_url']

  with api.context(cwd=workdir):
    return workdir.join(api.bot_update.ensure_checkout(
        gclient_config=gclient_config, patch=patch).json.output['root'])


def RunSteps(api, upstream_project, downstream_project):
  workdir_base = api.path['cache'].join('recipe_roll_tryjob')
  upstream_workdir = workdir_base.join(upstream_project)
  downstream_workdir = workdir_base.join(downstream_project)

  project_data = api.luci_config.get_projects()

  upstream_checkout = _checkout_project(
      api, upstream_workdir, upstream_project,
      project_data[upstream_project], patch=False)
  downstream_checkout = _checkout_project(
      api, downstream_workdir, downstream_project,
      project_data[downstream_project], patch=False)

  downstream_recipes_path = _get_recipes_path(
      api, downstream_checkout.join('infra', 'config', 'recipes.cfg'))
  downstream_recipes_py = downstream_checkout.join(
      downstream_recipes_path, 'recipes.py')

  try:
    orig_downstream_test = api.python('test (without patch)',
        downstream_recipes_py,
        ['-O', '%s=%s' % (upstream_project, upstream_checkout),
         'test', 'run', '--json', api.json.output()],
        step_test_data=lambda: api.json.test_api.output({}))
  except api.step.StepFailure as ex:
    orig_downstream_test = ex.result

  try:
    orig_downstream_train = api.python('train (without patch)',
        downstream_recipes_py,
        ['-O', '%s=%s' % (upstream_project, upstream_checkout),
         'test', 'train', '--json', api.json.output()],
        step_test_data=lambda: api.json.test_api.output({}))
  except api.step.StepFailure as ex:
    orig_downstream_train = ex.result

  _checkout_project(
       api, upstream_workdir, upstream_project,
       project_data[upstream_project], patch=True)

  try:
    patched_downstream_test = api.python('test (with patch)',
        downstream_recipes_py,
        ['-O', '%s=%s' % (upstream_project, upstream_checkout),
         'test', 'run', '--json', api.json.output()],
        step_test_data=lambda: api.json.test_api.output({}))
  except api.step.StepFailure as ex:
    patched_downstream_test = ex.result

  try:
    patched_downstream_train = api.python('train (with patch)',
        downstream_recipes_py,
        ['-O', '%s=%s' % (upstream_project, upstream_checkout),
         'test', 'train', '--json', api.json.output()],
        step_test_data=lambda: api.json.test_api.output({}))
  except api.step.StepFailure as ex:
    patched_downstream_train = ex.result

  if patched_downstream_test.retcode == 0:
    return

  try:
    test_diff = api.python('diff (test)',
        downstream_recipes_py,
        ['test', 'diff',
         '--baseline', api.json.input(orig_downstream_test.json.output),
         '--actual', api.json.input(patched_downstream_test.json.output)])
  except api.step.StepFailure as ex:
    test_diff = ex.result

  if test_diff.retcode == 0:
    return

  try:
    train_diff = api.python('diff (train)',
        downstream_recipes_py,
        ['test', 'diff',
         '--baseline', api.json.input(orig_downstream_train.json.output),
         '--actual', api.json.input(patched_downstream_train.json.output)])
  except api.step.StepFailure as ex:
    train_diff = ex.result

  if train_diff.retcode == 0:
    return

  manual_change_footer = 'Recipe-Manual-Change-%s' % downstream_project
  footer_contents = api.tryserver.get_footer(manual_change_footer)
  if footer_contents:
    api.python.succeeding_step(
        'result', 'Recognized manual change ACK footer (%r).' % footer_contents)
  else:
    api.python.failing_step(
        'result',
        ('Add %s footer to the CL to acknowledge the change will require '
         'manual code changes in %r repo') % (
             manual_change_footer, downstream_project))


def GenTests(api):
  yield (
    api.test('basic') +
    api.properties.generic(
        upstream_project='recipe_engine', downstream_project='depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools'))
  )

  yield (
    api.test('without_patch_test_fail') +
    api.properties.generic(
        upstream_project='recipe_engine', downstream_project='depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('test (without patch)', retcode=1)
  )

  yield (
    api.test('without_patch_train_fail') +
    api.properties.generic(
        upstream_project='recipe_engine', downstream_project='depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('train (without patch)', retcode=1)
  )

  yield (
    api.test('with_patch_test_fail') +
    api.properties.generic(
        upstream_project='recipe_engine', downstream_project='depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('test (with patch)', retcode=1)
  )

  yield (
    api.test('with_patch_train_fail') +
    api.properties.generic(
        upstream_project='recipe_engine', downstream_project='depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('train (with patch)', retcode=1)
  )

  yield (
    api.test('diff_test_fail') +
    api.properties.generic(
        upstream_project='recipe_engine', downstream_project='depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1)
  )

  yield (
    api.test('diff_train_fail') +
    api.properties.tryserver(
        upstream_project='recipe_engine', downstream_project='depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.step_data('diff (train)', retcode=1) +
    api.override_step_data(
        'git_cl description', stdout=api.raw_io.output('')) +
    api.override_step_data(
        'parse description', api.json.output({}))
  )

  yield (
    api.test('diff_train_fail_ack') +
    api.properties.tryserver(
        upstream_project='recipe_engine', downstream_project='depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.step_data('diff (train)', retcode=1) +
    api.override_step_data(
        'git_cl description', stdout=api.raw_io.output(
            'Recipe-Manual-Change-depot_tools: ack')) +
    api.override_step_data(
        'parse description', api.json.output(
            {'Recipe-Manual-Change-depot_tools': ['ack']}))
  )
