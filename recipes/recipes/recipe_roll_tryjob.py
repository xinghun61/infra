# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property


DEPS = [
  'recipe_engine/buildbucket',
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/runtime',
  'recipe_engine/step',

  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/tryserver',
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
KNOWN_FOOTERS = [NONTRIVIAL_ROLL_FOOTER, MANUAL_CHANGE_FOOTER, BYPASS_FOOTER]

FOOTER_ADD_TEMPLATE = '''

Add

    {footer}: {down_id}

To your CL message.

'''

MANUAL_CHANGE_MSG = '''
This means that your upstream CL (this one) will require MANUAL CODE CHANGES
in the downstream repo {down_id!r}. Best practice is to prepare all downstream
changes before landing the upstream CL, using:

    {down_id}/{down_recipes} -O {up_id}=/path/to/local/{up_id} test train

When that CL has been reviewed, you can land this upstream change. Once the
upstream change lands, roll it into your downstream CL:

    {down_id}/recipes.py manual_roll   # may require running multiple times.

Re-train expectations and upload the expectations plus the roll to your
downstream CL. It's customary to copy the outputs of manual_roll to create
a changelog to attach to the downstream CL as well to help reviewers understand
what the roll contains.
'''.strip()

NONTRIVIAL_CHANGE_MSG = '''
This means that your upstream CL (this one) will change the EXPECTATION FILES
in the downstream repo {down_id!r}.

The recipe roller will automatically prepare the non-trivial CL and will upload
it with `git cl upload --r-owners` to the downstream repo. Best practice is to
review this non-trivial roll CL to ensure that the expectations you see there
are expected.
'''

EXTRA_MSG = {
  NONTRIVIAL_ROLL_FOOTER: NONTRIVIAL_CHANGE_MSG,
  MANUAL_CHANGE_FOOTER: MANUAL_CHANGE_MSG,
}


def _checkout_project(
    api, workdir, project, url, patch, revision=None, name=None):
  api.file.ensure_directory('%s checkout' % project, workdir)

  gclient_config = api.gclient.make_config()
  gclient_config.got_revision_reverse_mapping['got_revision'] = project
  soln = gclient_config.solutions.add()
  soln.name = project
  soln.url = url
  soln.revision = revision

  with api.context(cwd=workdir):
    ret = api.bot_update.ensure_checkout(
        gclient_config=gclient_config, patch=patch, manifest_name=name)
    with api.context(cwd=workdir.join(project)):
      # Clean out those stale pyc's!
      api.git('clean', '-xf')
    return workdir.join(ret.json.output['root'])


def _find_footer(api, repo_id):
  all_footers = api.tryserver.get_footers()

  if BYPASS_FOOTER in all_footers:
    api.python.succeeding_step(
        'BYPASS ENABLED',
        'Roll tryjob bypassed for %r' % (
          # It's unlikely that there's more than one value, but just in case...
          ', '.join(all_footers[BYPASS_FOOTER]),))
    return None, True

  found_set = set()
  for footer in KNOWN_FOOTERS:
    values = all_footers.get(footer, ())
    if repo_id in values:
      found_set.add(footer)

  if len(found_set) > 1:
    api.python.failing_step(
        'Too many footers for %r' % (repo_id,),
        'Found too many footers in CL message:\n' + (
          '\n'.join(' * '+f for f in sorted(found_set)))
    )

  return found_set.pop() if found_set else None, False


def _find_recipes_py(api, repo_path):
  recipes_cfg = api.file.read_json(
      'parse recipes.cfg',
      repo_path.join('infra', 'config', 'recipes.cfg'),
      test_data={
        'recipes_path': 'some/path',
      })
  return api.path.join(recipes_cfg.get('recipes_path', ''), 'recipes.py')


def RunSteps(api, upstream_id, upstream_url, downstream_id, downstream_url):
  # NOTE: this recipe is only useful as a tryjob with patch applied against
  # upstream repo, which means upstream_url must always match that specified in
  # api.buildbucket.build.input.gerrit_changes[0]. upstream_url remains as a
  # required parameter for symmetric input for upstream/downstream.
  # TODO: figure out upstream_id from downstream's repo recipes.cfg file using
  # patch and deprecated both upstream_id and upstream_url parameters.
  workdir_base = api.path['cache'].join('builder')

  # First, check to see if the user has bypassed this tryjob's analysis
  # entirely.
  actual_footer, bypass = _find_footer(api, downstream_id)
  if bypass:
    return

  # If not, we run a 'train' on the downstream repo, using the upstream
  # checkout.
  #
  # If the train fails, we require a Manual-Change footer
  # If the train creates a diff, we require a Nontrivial-Roll footer
  # If the train is clean, we require no footers
  upstream_checkout = _checkout_project(
      api, workdir_base.join(upstream_id), upstream_id, upstream_url,
      patch=True, name="upstream")
  downstream_checkout = _checkout_project(
      api, workdir_base.join(downstream_id), downstream_id, downstream_url,
      patch=False, name="downstream")

  expected_footer = None
  recipes_relpath = _find_recipes_py(api, downstream_checkout)
  try:
    api.python('train recipes',
        downstream_checkout.join(recipes_relpath),
        ['-O', '%s=%s' % (upstream_id, upstream_checkout), 'test', 'train',
         '--no-docs'])

    with api.context(cwd=downstream_checkout):
      # This has the benefit of showing the expectation diff to the user.
      dirty_check = api.git(
          'diff', '--exit-code', name='post-train diff', ok_ret='any')

    if dirty_check.retcode != 0:
      dirty_check.presentation.status = 'FAILURE'
      expected_footer = NONTRIVIAL_ROLL_FOOTER
  except api.step.StepFailure:
    expected_footer = MANUAL_CHANGE_FOOTER

  # Either expected_footer and actual_footer are both None or both matching
  # footers.
  if expected_footer == actual_footer:
    if expected_footer:
      msg = (
        'CL message contains correct footer (%r) for this repo.'
      ) % expected_footer
    else:
      msg = 'CL is trivial and message contains no footers for this repo.'
    api.python.succeeding_step('Roll OK', msg)
    return

  # trivial roll, but user has footer in CL message.
  if expected_footer is None and actual_footer is not None:
    api.python.failing_step(
        'UNEXPECTED FOOTER IN CL MESSAGE',
        'Change is trivial, but found %r footer' % (actual_footer,))

  # nontrivial/manual roll, but user has wrong footer in CL message.
  if expected_footer is not None and actual_footer is not None:
    api.python.failing_step(
        'WRONG FOOTER IN CL MESSAGE',
        'Change reqires %r, but found %r footer' % (
          expected_footer, actual_footer,))

  # expected != None at this point, so actual_footer must be None
  msg = FOOTER_ADD_TEMPLATE + EXTRA_MSG[expected_footer]
  api.python.failing_step(
      'MISSING FOOTER IN CL MESSAGE',
      msg.format(
          footer=expected_footer,
          up_id=upstream_id,
          down_id=downstream_id,
          down_recipes=recipes_relpath,
      ))


def GenTests(api):
  def test(name, *footers):
    upstream_id = 'recipe_engine'
    downstream_id = 'depot_tools'
    repo_urls = {
      'build':
      'https://chromium.googlesource.com/chromium/tools/build',
      'depot_tools':
      'https://chromium.googlesource.com/chromium/tools/depot_tools',
      'recipe_engine':
      'https://chromium.googlesource.com/infra/luci/recipes-py',
    }
    return (
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
      + api.override_step_data('gerrit changes', api.json.output([{
        'revisions': {
          'deadbeef': {'_number': 12, 'commit': {'message': ''}},
        }
      }]))
      + api.step_data(
          'parse description', api.json.output({
            k: ['Reasons' if k == BYPASS_FOOTER else downstream_id]
            for k in footers
          }))
    )

  yield (
    test('find_trivial_roll')
  )

  yield (
    test('bypass', BYPASS_FOOTER)
    + api.post_check(lambda check, steps: check('BYPASS ENABLED' in steps))
  )

  yield (
    test('too_many_footers', MANUAL_CHANGE_FOOTER, NONTRIVIAL_ROLL_FOOTER)
    + api.post_check(lambda check, steps: check(
        "Too many footers for 'depot_tools'" in steps
    ))
  )

  yield (
    test('find_trivial_roll_unexpected', MANUAL_CHANGE_FOOTER)
    + api.post_check(lambda check, steps: check(
        'UNEXPECTED FOOTER IN CL MESSAGE' in steps
    ))
  )

  yield (
    test('find_manual_roll_missing')
    + api.step_data('train recipes', retcode=1)
    + api.post_check(lambda check, steps: check(
        MANUAL_CHANGE_FOOTER in steps['MISSING FOOTER IN CL MESSAGE'].step_text
    ))
  )

  yield (
    test('find_manual_roll_wrong', NONTRIVIAL_ROLL_FOOTER)
    + api.step_data('train recipes', retcode=1)
    + api.post_check(lambda check, steps: check(
        MANUAL_CHANGE_FOOTER in steps['WRONG FOOTER IN CL MESSAGE'].step_text
    ))
  )

  yield (
    test('find_non_trivial_roll')
    + api.step_data('post-train diff', retcode=1)
    + api.post_check(lambda check, steps: check(
      NONTRIVIAL_ROLL_FOOTER in steps['MISSING FOOTER IN CL MESSAGE'].step_text
    ))
  )

  yield (
    test('non_trivial_roll_match', NONTRIVIAL_ROLL_FOOTER)
    + api.step_data('post-train diff', retcode=1)
  )
