# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property


DEPS = [
  'build/luci_config',
  'build/puppet_service_account',
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

  # To generate an auth token for running locally, run
  #   infra/cipd/authutil token
  'auth_token': Property(default=None),
  'service_account': Property(
      default=None, kind=str,
      help='The name of the service account to use when running on a bot. For '
           'example, if you use "recipe-roll-tester", this recipe will try '
           'to use the /creds/service_accounts/service-account-'
           'recipe-roll-tester.json service account')
}


NONTRIVIAL_ROLL_FOOTER = 'Recipe-Nontrivial-Roll'


MANUAL_CHANGE_FOOTER = 'Recipe-Manual-Change'


BYPASS_FOOTER = 'Recipe-Tryjob-Bypass-Reason'


def _get_recipe_dep(api, recipes_cfg_path, project):
  """Extracts url and revision of |project| from given recipes.cfg."""
  current_cfg = api.json.read(
    'read recipes.cfg',
    recipes_cfg_path, step_test_data=lambda: api.json.test_api.output({}))
  dep = current_cfg.json.output.get('deps', {}).get(project, {})
  return dep.get('url'), dep.get('revision')


def _checkout_project(
    api, workdir, project, url, patch, revision=None, name=None):
  api.file.ensure_directory('%s checkout' % project, workdir)

  gclient_config = api.gclient.make_config()
  gclient_config.got_revision_reverse_mapping['got_revision'] = project
  s = gclient_config.solutions.add()
  s.name = project
  s.url = url
  if revision:
    s.revision = revision

  with api.context(cwd=workdir):
    return api.bot_update.ensure_checkout(
        gclient_config=gclient_config, patch=patch, manifest_name=name)


def RunSteps(
    api, upstream_project, downstream_project, auth_token, service_account):
  workdir_base = api.path['cache'].join('recipe_roll_tryjob')
  upstream_workdir = workdir_base.join(upstream_project)
  downstream_workdir = workdir_base.join(downstream_project)
  engine_workdir = workdir_base.join('recipe_engine')

  api.luci_config.set_config('basic')
  if service_account:
    auth_token = api.puppet_service_account.get_access_token(service_account)
  if auth_token:
    api.luci_config.c.auth_token = auth_token

  project_data = api.luci_config.get_projects()

  upstream_checkout_step = _checkout_project(
      api, upstream_workdir, upstream_project,
      project_data[upstream_project]['repo_url'], patch=False, name="upstream")
  downstream_checkout_step = _checkout_project(
      api, downstream_workdir, downstream_project,
      project_data[downstream_project]['repo_url'], patch=False,
      name="downstream")

  upstream_checkout = upstream_workdir.join(
      upstream_checkout_step.json.output['root'])
  downstream_checkout = downstream_workdir.join(
      downstream_checkout_step.json.output['root'])

  # Use recipe engine version matching the upstream one.
  # This most closely simulates rolling the upstream change.
  if upstream_project == 'recipe_engine':
    engine_checkout = upstream_checkout
  else:
    engine_url, engine_revision = _get_recipe_dep(
        api, upstream_checkout.join('infra', 'config', 'recipes.cfg'),
        'recipe_engine')

    engine_checkout_step = _checkout_project(
        api, engine_workdir, 'recipe_engine',
        engine_url, revision=engine_revision, patch=False, name="engine")
    engine_checkout = engine_workdir.join(
        engine_checkout_step.json.output['root'])

  downstream_recipes_cfg = downstream_checkout.join(
      'infra', 'config', 'recipes.cfg')
  recipes_py = engine_checkout.join('recipes.py')

  try:
    orig_downstream_test = api.python('test (without patch)',
        recipes_py,
        ['--package', downstream_recipes_cfg,
         '-O', '%s=%s' % (upstream_project, upstream_checkout),
         'test', 'run', '--json', api.json.output()],
        step_test_data=lambda: api.json.test_api.output({}))
  except api.step.StepFailure as ex:
    orig_downstream_test = ex.result

  try:
    orig_downstream_train = api.python('train (without patch)',
        recipes_py,
        ['--package', downstream_recipes_cfg,
         '-O', '%s=%s' % (upstream_project, upstream_checkout),
         'test', 'train', '--json', api.json.output()],
        step_test_data=lambda: api.json.test_api.output({}))
  except api.step.StepFailure as ex:
    orig_downstream_train = ex.result

  upstream_revision = upstream_checkout_step.json.output[
      'manifest'][upstream_project]['revision']
  _checkout_project(
       api, upstream_workdir, upstream_project,
       project_data[upstream_project]['repo_url'], patch=True,
       revision=upstream_revision, name="upstream_patched")

  downstream_revision = downstream_checkout_step.json.output[
      'manifest'][downstream_project]['revision']
  _checkout_project(
       api, downstream_workdir, downstream_project,
       project_data[downstream_project]['repo_url'], patch=False,
       revision=downstream_revision, name="downstream_patched")

  # Since we patched upstream repo (potentially including recipes.cfg),
  # make sure to keep our recipe engine checkout in sync.
  if upstream_project != 'recipe_engine':
    engine_url, engine_revision = _get_recipe_dep(
        api, upstream_checkout.join('infra', 'config', 'recipes.cfg'),
        'recipe_engine')
    _checkout_project(
        api, engine_workdir, 'recipe_engine',
        engine_url, revision=engine_revision, patch=False,
        name="engine_patched")

  try:
    patched_downstream_test = api.python('test (with patch)',
        recipes_py,
        ['--package', downstream_recipes_cfg,
         '-O', '%s=%s' % (upstream_project, upstream_checkout),
         'test', 'run', '--json', api.json.output()],
        step_test_data=lambda: api.json.test_api.output({}))
  except api.step.StepFailure as ex:
    patched_downstream_test = ex.result

  try:
    patched_downstream_train = api.python('train (with patch)',
        recipes_py,
        ['--package', downstream_recipes_cfg,
         '-O', '%s=%s' % (upstream_project, upstream_checkout),
         'test', 'train', '--json', api.json.output()],
        step_test_data=lambda: api.json.test_api.output({}))
  except api.step.StepFailure as ex:
    patched_downstream_train = ex.result

  if patched_downstream_test.retcode == 0:
    return

  try:
    test_diff = api.python('diff (test)',
        recipes_py,
        ['--package', downstream_recipes_cfg,
         'test', 'diff',
         '--baseline', api.json.input(orig_downstream_test.json.output),
         '--actual', api.json.input(patched_downstream_test.json.output)])
  except api.step.StepFailure as ex:
    test_diff = ex.result

  if test_diff.retcode == 0:
    return

  cl_footers = api.tryserver.get_footers()

  nontrivial_roll_footer = cl_footers.get(NONTRIVIAL_ROLL_FOOTER, [])
  manual_change_footer = cl_footers.get(MANUAL_CHANGE_FOOTER, [])
  bypass_footer = cl_footers.get(BYPASS_FOOTER, [])

  if downstream_project in manual_change_footer:
    api.python.succeeding_step(
        'result',
        ('Recognized %s footer for %s.' %
             (MANUAL_CHANGE_FOOTER, downstream_project)))
  elif downstream_project in nontrivial_roll_footer:
    api.python.succeeding_step(
        'result',
        ('Recognized %s footer for %s.' %
             (NONTRIVIAL_ROLL_FOOTER, downstream_project)))

  try:
    train_diff = api.python('diff (train)',
        recipes_py,
        ['--package', downstream_recipes_cfg,
         'test', 'diff',
         '--baseline', api.json.input(orig_downstream_train.json.output),
         '--actual', api.json.input(patched_downstream_train.json.output)])
  except api.step.StepFailure as ex:
    train_diff = ex.result

  # In theory we could return early when bypass footer is present. Executing
  # test steps anyway helps provide more data points for this recipe's logic.
  if bypass_footer:
    api.python.succeeding_step(
        'result',
        ('Recognized %s footer: %s.' %
             (BYPASS_FOOTER, '; '.join(bypass_footer))))
    return

  if train_diff.retcode == 0:
    if (downstream_project not in manual_change_footer and
        downstream_project not in nontrivial_roll_footer):
      api.python.failing_step(
          'result',
          ('Add "%s: %s" footer to the CL to acknowledge the change will '
           'require nontrivial roll in %r repo') % (
               NONTRIVIAL_ROLL_FOOTER, downstream_project, downstream_project))
    return

  if downstream_project in manual_change_footer:
    api.python.succeeding_step(
        'result',
        ('Recognized %s footer for %s.' %
             (MANUAL_CHANGE_FOOTER, downstream_project)))
  else:
    api.python.failing_step(
        'result',
        ('Add "%s: %s" footer to the CL to acknowledge the change will require '
         'manual code changes in %r repo') % (
             MANUAL_CHANGE_FOOTER, downstream_project, downstream_project))


def GenTests(api):
  yield (
    api.test('basic') +
    api.properties.generic(
        upstream_project='recipe_engine',
        downstream_project='depot_tools',
        service_account='recipe-roll-tester') +
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
    api.properties.tryserver(
        upstream_project='recipe_engine',
        downstream_project='depot_tools',
        gerrit_project='chromium/tools/depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.override_step_data(
      'gerrit changes', api.json.output(
        [{'revisions': {1: {'_number': 12, 'commit': {'message': ''}}}}])) +
    api.override_step_data(
        'parse description', api.json.output({}))
  )

  yield (
    api.test('diff_test_fail_ack') +
    api.properties.tryserver(
        upstream_project='recipe_engine',
        downstream_project='depot_tools',
        gerrit_project='chromium/tools/depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.override_step_data(
      'gerrit changes', api.json.output(
        [{'revisions': {1: {'_number': 12, 'commit': {
          'message': 'Recipe-Nontrivial-Roll: depot_tools'}}}}])) +
    api.override_step_data(
        'parse description', api.json.output(
            {'Recipe-Nontrivial-Roll': ['depot_tools']}))
  )

  yield (
    api.test('diff_train_fail') +
    api.properties.tryserver(
        upstream_project='recipe_engine',
        downstream_project='depot_tools',
        gerrit_project='chromium/tools/depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.step_data('diff (train)', retcode=1) +
    api.override_step_data(
      'gerrit changes', api.json.output(
        [{'revisions': {1: {'_number': 12, 'commit': {
          'message': 'Recipe-Nontrivial-Roll: depot_tools'}}}}])) +
    api.override_step_data(
        'parse description', api.json.output(
            {'Recipe-Nontrivial-Roll': ['depot_tools']}))
  )

  yield (
    api.test('diff_train_fail_ack') +
    api.properties.tryserver(
        upstream_project='recipe_engine',
        downstream_project='depot_tools',
        gerrit_project='chromium/tools/depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.step_data('diff (train)', retcode=1) +
    api.override_step_data(
      'gerrit changes', api.json.output(
        [{'revisions': {1: {'_number': 12, 'commit': {
          'message': 'Recipe-Manual-Change: depot_tools'}}}}])) +
    api.override_step_data(
        'parse description', api.json.output(
            {'Recipe-Manual-Change': ['depot_tools']}))
  )

  yield (
    api.test('diff_train_fail_ack_engine_checkout') +
    api.properties.tryserver(
        upstream_project='depot_tools',
        downstream_project='build',
        gerrit_project='chromium/tools/build') +
    api.luci_config.get_projects(('depot_tools', 'build')) +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.step_data('diff (train)', retcode=1) +
    api.override_step_data(
      'gerrit changes', api.json.output(
        [{'revisions': {1: {'_number': 12, 'commit': {
          'message': 'Recipe-Manual-Change: build'}}}}])) +
    api.override_step_data(
        'parse description', api.json.output(
            {'Recipe-Manual-Change': ['build']}))
  )

  yield (
    api.test('bypass') +
    api.properties.tryserver(
        upstream_project='recipe_engine',
        downstream_project='depot_tools',
        gerrit_project='chromium/tools/depot_tools') +
    api.luci_config.get_projects(('recipe_engine', 'depot_tools')) +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.override_step_data(
      'gerrit changes', api.json.output(
        [{'revisions': {1: {'_number': 12, 'commit': {
          'message': 'Recipe-Tryjob-Bypass-Reason: Autoroller'}}}}])) +
    api.override_step_data(
        'parse description', api.json.output(
            {'Recipe-Tryjob-Bypass-Reason': ['Autoroller']}))
  )
