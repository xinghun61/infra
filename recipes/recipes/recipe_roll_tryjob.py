# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Rolls recipes.cfg dependencies."""

DEPS = [
  'build/recipe_tryjob',
  'build/luci_config',
  'recipe_engine/json',
  'recipe_engine/properties',
  'recipe_engine/raw_io',
  'recipe_engine/step',
]

from recipe_engine.recipe_api import Property


def get_auth_token(api, service_account=None):
  """
  Get an auth token; this assumes the user is logged in with the infra
  authutil command line utility.

  If service_account is provided, that service account will be used when calling
  authutil.
  """
  cmd = ['/opt/infra-tools/authutil', 'token']
  if service_account: # pragma: no cover
      cmd.extend([
          '-service-account-json='
          '/creds/service_accounts/service-account-%s.json' % service_account])

  result = api.step(
      'Get auth token', cmd,
      stdout=api.raw_io.output(),
      step_test_data=lambda: api.raw_io.test_api.stream_output('ya29.foobar'))
  return result.stdout.strip()


PROPERTIES = {
  'patches': Property(kind=str, param_name='patches_raw', default="",
                      help="Patches to apply. Format is"
                      "project1:https://url.to.codereview/123456#ps01 where"
                      "url.to.codereview is the address of the code review site"
                      ", 123456 is the issue number, and ps01 is the patchset"
                      "number"),
  # This recipe can be used as a tryjob by setting the rietveld, issue, and
  # patchset properties, like a normal tryjob. If those are set, it will use
  # those, as well as any data sent in the regular properties, as patches to
  # apply.
  "rietveld": Property(kind=str, default="",
                       help="The Rietveld instance the issue is from"),
  "issue": Property(kind=str, default=None,
                    help="The Rietveld issue number to pull data from"),
  "patchset": Property(kind=str, default=None,
                       help="The patchset number for the supplied issue"),
  "patch_project": Property(
      kind=str, default=None,
      help="The luci-config name of the project this patch belongs to"),

  # To generate an auth token for running locally, run
  #   infra/go/bin/authutil login
  'auth_token': Property(
      default=None, help="The auth_token to use to talk to luci-config. "
      "Mutually exclusive with the service_account property"),
  'service_account': Property(
      default=None, kind=str,
      help="The name of the service account to use when running on a bot. For "
           "example, if you use \"recipe-roller\", this recipe will try to use "
           "the /creds/service_accounts/service-account-recipe-roller.json "
           "service account")
}

def RunSteps(api, patches_raw, rietveld, issue, patchset, patch_project,
             auth_token, service_account):
  # TODO(martiniss): use real types
  issue = int(issue) if issue else None
  patchset = int(patchset) if patchset else None

  if not auth_token:
    auth_token = get_auth_token(api, service_account)
  else: # pragma: no cover
    assert not service_account, (
        "Only one of \"service_account\" and \"auth_token\" may be set")

  api.luci_config.c.auth_token = auth_token

  api.recipe_tryjob.run_tryjob(
      patches_raw, rietveld, issue, patchset, patch_project)



def GenTests(api):
  yield (
      api.test('basic') +
      api.luci_config.get_projects(('recipe_engine', 'build')) +
      api.luci_config.get_project_config(
          'build', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('build')) +
      api.luci_config.get_project_config(
          'recipe_engine', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('recipe_engine'))
  )

  yield (
      api.test('one_patch') +
      api.luci_config.get_projects(('recipe_engine', 'build')) +
      api.luci_config.get_project_config(
          'build', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('build')) +
      api.luci_config.get_project_config(
          'recipe_engine', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('recipe_engine')) +
      api.properties(patches="build:https://fake.code.review/123456#ps1") +
      api.override_step_data(
          'git_cl description (build)', stdout=api.raw_io.output(
              "")) +
      api.override_step_data(
          'parse description', api.json.output(
              {}))
  )

  yield (
      api.test('three_patches') +
      api.luci_config.get_projects(('recipe_engine', 'build', 'depot_tools')) +
      api.luci_config.get_project_config(
          'build', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config(
              'build', ['depot_tools', 'recipe_engine'])) +
      api.luci_config.get_project_config(
          'recipe_engine', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('recipe_engine')) +
      api.luci_config.get_project_config(
          'depot_tools', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config(
              'depot_tools', ['recipe_engine'])) +
      api.properties(
          patches="depot_tools:https://fake.code.review/123456#ps1,"
                  "build:https://fake.code.review/789999#ps2") +
      api.override_step_data(
          'git_cl description (build)', stdout=api.raw_io.output(
              "")) +
      api.override_step_data(
          'git_cl description (depot_tools)', stdout=api.raw_io.output(
              "")) +
      api.override_step_data(
          'parse description', api.json.output(
              {})) +
      api.override_step_data(
          'parse description (2)', api.json.output(
              {}))
  )

  yield (
      api.test('three_patches_fail_not_ok') +
      api.luci_config.get_projects(('recipe_engine', 'build', 'depot_tools')) +
      api.luci_config.get_project_config(
          'build', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config(
              'build', ['depot_tools', 'recipe_engine'])) +
      api.luci_config.get_project_config(
          'recipe_engine', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('recipe_engine')) +
      api.luci_config.get_project_config(
          'depot_tools', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config(
              'depot_tools', ['recipe_engine'])) +
      api.properties(
          patches="depot_tools:https://fake.code.review/123456#ps1,"
                  "build:https://fake.code.review/789999#ps2") +
      api.override_step_data(
          'git_cl description (build)', stdout=api.raw_io.output(
              "")) +
      api.override_step_data(
          'git_cl description (depot_tools)', stdout=api.raw_io.output(
              "")) +
      api.override_step_data(
          'parse description', api.json.output(
              {})) +
      api.override_step_data(
          'parse description (2)', api.json.output(
              {})) +
      api.override_step_data("build tests", retcode=1)
  )

  yield (
      api.test('three_patches_fail_ok') +
      api.luci_config.get_projects(('recipe_engine', 'build', 'depot_tools')) +
      api.luci_config.get_project_config(
          'build', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config(
              'build', ['depot_tools', 'recipe_engine'])) +
      api.luci_config.get_project_config(
          'recipe_engine', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('recipe_engine')) +
      api.luci_config.get_project_config(
          'depot_tools', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config(
              'depot_tools', ['recipe_engine'])) +
      api.properties(
          patches="depot_tools:https://fake.code.review/123456#ps1,"
                  "build:https://fake.code.review/789999#ps2") +
      api.override_step_data(
          'git_cl description (build)', stdout=api.raw_io.output(
              "foo")) +
      api.override_step_data(
          'git_cl description (depot_tools)', stdout=api.raw_io.output(
              "Recipe-Tryjob-Bypass-Reason: best reason")) +
      api.override_step_data(
          'parse description', api.json.output(
              {'Recipe-Tryjob-Bypass-Reason': ['Best Reason']})) +
      api.override_step_data(
          'parse description (2)', api.json.output(
              {'Recipe-Tryjob-Bypass-Reason': []})) +
      api.override_step_data("build tests", retcode=1)
  )

  yield (
      api.test('bad_patches') +
      api.properties(
          patches="build:https://f.e.w/1#ps1,build:https://f.e.w/1#ps1")
  )

  yield (
      api.test('deps') +
      api.luci_config.get_projects(('recipe_engine', 'build')) +
      api.luci_config.get_project_config(
          'build', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('build', ['recipe_engine'])) +
      api.luci_config.get_project_config(
          'recipe_engine', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('recipe_engine')) +
      api.properties(
          patches="recipe_engine:https://fake.code.review/123456#ps1") +
      api.override_step_data(
          'parse description', api.json.output({})) +
      api.override_step_data(
          'git_cl description (recipe_engine)', stdout=api.raw_io.output(
              "foo"))
  )

  yield (
      api.test('tryjob') +
      api.properties(
        rietveld="https://fake.code.review",
        issue='12345678',
        patchset='1',
        patch_project="build",
      ) +
      api.luci_config.get_projects(('recipe_engine', 'build')) +
      api.luci_config.get_project_config(
          'build', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('build', ['recipe_engine'])) +
      api.luci_config.get_project_config(
          'recipe_engine', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('recipe_engine')) +
      api.override_step_data(
          'git_cl description (build)', stdout=api.raw_io.output(
              "")) +
      api.override_step_data(
          'parse description', api.json.output(
              {}))
  )

  yield (
      api.test('tryjob_dont_test_untouched_code') +
      api.properties(
        rietveld="https://fake.code.review",
        issue='12345678',
        patchset='1',
        patch_project="build",
      ) +
      api.luci_config.get_projects(('recipe_engine', 'build', 'foobar')) +
      api.luci_config.get_project_config(
          'build', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('build', ['recipe_engine'])) +
      api.luci_config.get_project_config(
          'recipe_engine', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('recipe_engine')) +
      api.override_step_data(
          'git_cl description (build)', stdout=api.raw_io.output(
              "")) +
      api.override_step_data(
          'parse description', api.json.output(
              {}))
  )

  yield (
      api.test('no_reference_builder') +
      api.luci_config.get_projects((
          'recipe_engine', 'build_limited_scripts_slave')) +
      api.luci_config.get_project_config(
          'build_limited_scripts_slave', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('build_limited_scripts_slave')) +
      api.luci_config.get_project_config(
          'recipe_engine', 'recipes.cfg',
          api.recipe_tryjob.make_recipe_config('recipe_engine')) +
      api.properties(
          patches="build_limited_scripts_slave:"
            "https://fake.code.review/123456#ps1") +
      api.override_step_data(
          'git_cl description (build_limited_scripts_slave)',
          stdout=api.raw_io.output("")) +
      api.override_step_data(
          'parse description', api.json.output(
              {}))
  )

