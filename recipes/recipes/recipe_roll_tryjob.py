# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property


DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/tryserver',
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/runtime',
  'recipe_engine/step',
]


PROPERTIES = {
  'upstream_id': Property(
      kind=str,
      help='ID of the project to patch'),
  'upstream_url': Property(
      kind=str,
      help='URL of git repo of the upstream project'),

  'downstream_id': Property(
      kind=str,
      help=('ID of the project that includes |upstream_id| in its recipes.cfg '
            'to be tested with upstream patch')),
  'downstream_url': Property(
      kind=str,
      help='URL of the git repo of the downstream project'),
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
    ret = api.bot_update.ensure_checkout(
        gclient_config=gclient_config, patch=patch, manifest_name=name)
    with api.context(cwd=workdir.join(project)):
      # Clean out those stale pyc's!
      api.git('clean', '-xf')
    return ret


def RunSteps(api, upstream_id, upstream_url, downstream_id, downstream_url):
  # NOTE: this recipe is only useful as a tryjob with patch applied against
  # upstream repo, which means upstream_url must always match that specified in
  # api.buildbucket.build.input.gerrit_changes[0]. upstream_url remains as a
  # required parameter for symmetric input for upstream/downstream.
  # TODO: figure out upstream_id from downstream's repo recipes.cfg file using
  # patch and deprecated both upstream_id and upstream_url parameters.
  workdir_base = api.path['cache'].join('recipe_roll_tryjob')
  upstream_workdir = workdir_base.join(upstream_id)
  downstream_workdir = workdir_base.join(downstream_id)
  engine_workdir = workdir_base.join('recipe_engine')

  upstream_checkout_step = _checkout_project(
      api, upstream_workdir, upstream_id, upstream_url,
      patch=False, name="upstream")
  downstream_checkout_step = _checkout_project(
      api, downstream_workdir, downstream_id, downstream_url,
      patch=False, name="downstream")

  upstream_checkout = upstream_workdir.join(
      upstream_checkout_step.json.output['root'])
  downstream_checkout = downstream_workdir.join(
      downstream_checkout_step.json.output['root'])

  # Use recipe engine version matching the upstream one.
  # This most closely simulates rolling the upstream change.
  if upstream_id == 'recipe_engine':
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
         '-O', '%s=%s' % (upstream_id, upstream_checkout),
         'test', 'run', '--json', api.json.output()],
        venv=True,
        step_test_data=lambda: api.json.test_api.output({}))
  except api.step.StepFailure as ex:
    orig_downstream_test = ex.result

  try:
    orig_downstream_train = api.python('train (without patch)',
        recipes_py,
        ['--package', downstream_recipes_cfg,
         '-O', '%s=%s' % (upstream_id, upstream_checkout),
         'test', 'train', '--json', api.json.output()],
        venv=True,
        step_test_data=lambda: api.json.test_api.output({}))
  except api.step.StepFailure as ex:
    orig_downstream_train = ex.result

  upstream_revision = upstream_checkout_step.json.output[
      'manifest'][upstream_id]['revision']
  _checkout_project(
       api, upstream_workdir, upstream_id, upstream_url,
       patch=True, revision=upstream_revision, name="upstream_patched")

  downstream_revision = downstream_checkout_step.json.output[
      'manifest'][downstream_id]['revision']
  _checkout_project(
       api, downstream_workdir, downstream_id, downstream_url,
       patch=False, revision=downstream_revision, name="downstream_patched")

  # Since we patched upstream repo (potentially including recipes.cfg),
  # make sure to keep our recipe engine checkout in sync.
  if upstream_id != 'recipe_engine':
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
         '-O', '%s=%s' % (upstream_id, upstream_checkout),
         'test', 'run', '--json', api.json.output()],
        venv=True,
        step_test_data=lambda: api.json.test_api.output({}))
  except api.step.StepFailure as ex:
    patched_downstream_test = ex.result

  try:
    patched_downstream_train = api.python('train (with patch)',
        recipes_py,
        ['--package', downstream_recipes_cfg,
         '-O', '%s=%s' % (upstream_id, upstream_checkout),
         'test', 'train', '--json', api.json.output()],
        venv=True,
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
         '--actual', api.json.input(patched_downstream_test.json.output)],
        venv=True)
  except api.step.StepFailure as ex:
    test_diff = ex.result

  if test_diff.retcode == 0:
    return

  cl_footers = api.tryserver.get_footers()

  nontrivial_roll_footer = cl_footers.get(NONTRIVIAL_ROLL_FOOTER, [])
  manual_change_footer = cl_footers.get(MANUAL_CHANGE_FOOTER, [])
  bypass_footer = cl_footers.get(BYPASS_FOOTER, [])

  if downstream_id in manual_change_footer:
    api.python.succeeding_step(
        'result',
        ('Recognized %s footer for %s.' %
             (MANUAL_CHANGE_FOOTER, downstream_id)))
  elif downstream_id in nontrivial_roll_footer:
    api.python.succeeding_step(
        'result',
        ('Recognized %s footer for %s.' %
             (NONTRIVIAL_ROLL_FOOTER, downstream_id)))

  try:
    train_diff = api.python('diff (train)',
        recipes_py,
        ['--package', downstream_recipes_cfg,
         'test', 'diff',
         '--baseline', api.json.input(orig_downstream_train.json.output),
         '--actual', api.json.input(patched_downstream_train.json.output)],
        venv=True)
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
    if (downstream_id not in manual_change_footer and
        downstream_id not in nontrivial_roll_footer):
      api.python.failing_step(
          'result',
          ('Add "%s: %s" footer to the CL to acknowledge the change will '
           'require nontrivial roll in %r repo') % (
               NONTRIVIAL_ROLL_FOOTER, downstream_id, downstream_id))
    return

  if downstream_id in manual_change_footer:
    api.python.succeeding_step(
        'result',
        ('Recognized %s footer for %s.' %
             (MANUAL_CHANGE_FOOTER, downstream_id)))
  else:
    api.python.failing_step(
        'result',
        ('Add "%s: %s" footer to the CL to acknowledge the change will require '
         'manual code changes in %r repo') % (
             MANUAL_CHANGE_FOOTER, downstream_id, downstream_id))


def GenTests(api):
  def test(name, upstream_id='recipe_engine', downstream_id='depot_tools',
           cl_description=None):
    repo_urls = {
      'build':
        'https://chromium.googlesource.com/chromium/tools/build',
      'depot_tools':
        'https://chromium.googlesource.com/chromium/tools/depot_tools',
      'recipe_engine':
        'https://chromium.googlesource.com/infra/luci/recipes-py',
    }
    res = (
        api.test(name)
        + api.runtime(is_luci=True, is_experimental=False)
        + api.properties(
            upstream_id=upstream_id,
            upstream_url=repo_urls[upstream_id],
            downstream_id=downstream_id,
            downstream_url=repo_urls[downstream_id])
        + api.buildbucket.try_build(
            git_repo=repo_urls[upstream_id],
            change_number=456789,
            patch_set=12)
    )
    if cl_description:
      res += api.override_step_data('gerrit changes', api.json.output([{
        'revisions': {
            'deadbeef': {'_number': 12, 'commit': {'message': cl_description}},
         }
      }]))
    return res

  yield (
    test('basic')
  )

  yield (
    test('without_patch_test_fail') +
    api.step_data('test (without patch)', retcode=1)
  )

  yield (
    test('without_patch_train_fail') +
    api.step_data('train (without patch)', retcode=1)
  )

  yield (
    test('with_patch_test_fail') +
    api.step_data('test (with patch)', retcode=1)
  )

  yield (
    test('with_patch_train_fail') +
    api.step_data('train (with patch)', retcode=1)
  )

  yield (
    test('diff_test_fail', cl_description='No-Footers.') +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.override_step_data('parse description', api.json.output({}))
  )

  yield (
    test('diff_test_fail_ack',
         cl_description='Recipe-Nontrivial-Roll: depot_tools') +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.override_step_data(
        'parse description', api.json.output(
            {'Recipe-Nontrivial-Roll': ['depot_tools']}))
  )

  yield (
    test('diff_train_fail',
         cl_description='Recipe-Nontrivial-Roll: depot_tools') +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.step_data('diff (train)', retcode=1) +
    api.override_step_data(
        'parse description', api.json.output(
            {'Recipe-Nontrivial-Roll': ['depot_tools']}))
  )

  yield (
    test('diff_train_fail_ack',
         cl_description='Recipe-Manual-Change: depot_tools') +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.step_data('diff (train)', retcode=1) +
    api.override_step_data(
        'parse description', api.json.output(
            {'Recipe-Manual-Change': ['depot_tools']}))
  )

  yield (
    test('diff_train_fail_ack_engine_checkout',
         upstream_id='depot_tools', downstream_id='build',
         cl_description='Recipe-Manual-Change: build') +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.step_data('diff (train)', retcode=1) +
    api.override_step_data(
        'parse description', api.json.output(
            {'Recipe-Manual-Change': ['build']}))
  )

  yield (
    test('bypass',
         cl_description='Recipe-Tryjob-Bypass-Reason: Autoroller') +
    api.step_data('test (with patch)', retcode=1) +
    api.step_data('diff (test)', retcode=1) +
    api.override_step_data(
        'parse description', api.json.output(
            {'Recipe-Tryjob-Bypass-Reason': ['Autoroller']}))
  )
