# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Rolls recipes.cfg dependencies for public projects."""

DEPS = [
  'recipe_autoroller',

  'build/luci_config',
  'build/puppet_service_account',

  'recipe_engine/json',
  'recipe_engine/properties',
  'recipe_engine/raw_io',
  'recipe_engine/step',
  'recipe_engine/time',
]

from recipe_engine import recipe_api


# Toposorted for best results.
# TODO(phajdan.jr): get the list of public projects from luci-config.
PROJECTS = [
  'depot_tools',
  'build',
  'franky',
  'infra',
  'skia',
  'skiabuildbot',
]


PROPERTIES = {
  'projects': recipe_api.Property(default=PROJECTS),

  # To generate an auth token for running locally, run
  #   infra/go/bin/authutil login
  'auth_token': recipe_api.Property(default=None),
  'service_account': recipe_api.Property(
      default=None, kind=str,
      help="The name of the service account to use when running on a bot. For "
           "example, if you use \"recipe-roller\", this recipe will try to use "
           "the /creds/service_accounts/service-account-recipe-roller.json "
           "service account")
}


def RunSteps(api, projects, auth_token, service_account):
  api.luci_config.set_config('basic')
  if not auth_token and service_account:
    auth_token = api.puppet_service_account.get_access_token(service_account)
  else:
    assert not service_account, (
        "Only one of \"service_account\" and \"auth_token\" may be set")
  api.luci_config.c.auth_token = auth_token

  api.recipe_autoroller.roll_projects(projects)


def GenTests(api):
  yield (
      api.test('basic') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build')
  )

  yield (
      api.test('with_auth') +
      api.properties(projects=['build'], service_account='recipe-roller') +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build')
  )

  yield (
      api.test('nontrivial') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build', trivial=False)
  )

  yield (
      api.test('empty') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build', empty=True)
  )

  yield (
      api.test('failure') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build', success=False)
  )

  yield (
      api.test('failed_upload') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build') +
      api.override_step_data(
          'build.git cl issue',
          api.json.output({'issue': None, 'issue_url': None}))
  )

  yield (
      api.test('repo_data_trivial_cq') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.recipe_cfg('build') +
      api.recipe_autoroller.repo_data(
          'build', trivial=True, status='commit',
          timestamp='2016-02-01T01:23:45') +
      api.time.seed(1451606400)
  )

  yield (
      api.test('repo_data_trivial_cq_stale') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.recipe_cfg('build') +
      api.recipe_autoroller.repo_data(
          'build', trivial=True, status='commit',
          timestamp='2016-02-01T01:23:45') +
      api.time.seed(1454371200)
  )

  yield (
      api.test('repo_data_trivial_closed') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.repo_data(
          'build', trivial=True, status='closed',
          timestamp='2016-02-01T01:23:45') +
      api.recipe_autoroller.roll_data('build') +
      api.time.seed(1451606400)
  )

  yield (
      api.test('repo_data_nontrivial_open') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.recipe_cfg('build') +
      api.recipe_autoroller.repo_data(
          'build', trivial=False, status='waiting',
          timestamp='2016-02-01T01:23:45') +
      api.time.seed(1451606400)
  )

  yield (
      api.test('repo_data_nontrivial_open_stale') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.recipe_cfg('build') +
      api.recipe_autoroller.repo_data(
          'build', trivial=False, status='waiting',
          timestamp='2016-02-01T01:23:45') +
      api.time.seed(1454371200)
  )

  yield (
      api.test('trivial_custom_tbr_no_dryrun') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build', trivial_commit=False)
  )

  yield (
      api.test('repo_disabled') +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data(
        'build', disable_reason='I am a water buffalo.')
  )
