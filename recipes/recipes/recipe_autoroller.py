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
  'recipe_engine/runtime',
  'recipe_engine/service_account',
  'recipe_engine/step',
  'recipe_engine/time',
]

from recipe_engine import recipe_api
from recipe_engine.post_process import MustRun


PROPERTIES = {
  'projects': recipe_api.Property(),
}


def RunSteps(api, projects):
  api.luci_config.set_config('basic')
  # If you are running this recipe locally and fail to access internal
  # repos, do "$ luci-auth login ...".
  api.luci_config.c.auth_token = (
      api.service_account.default().get_access_token())
  api.recipe_autoroller.roll_projects(projects)


def GenTests(api):
  yield (
      api.test('basic') +
      api.runtime(is_luci=True, is_experimental=False) +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build')
  )

  yield (
      api.test('with_auth') +
      api.runtime(is_luci=True, is_experimental=False) +
      api.properties(projects=['build'], service_account='recipe-roller') +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build')
  )

  yield (
      api.test('nontrivial') +
      api.runtime(is_luci=True, is_experimental=False) +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build', trivial=False)
  )

  yield (
      api.test('empty') +
      api.runtime(is_luci=True, is_experimental=False) +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build', empty=True)
  )

  yield (
      api.test('failure') +
      api.runtime(is_luci=True, is_experimental=False) +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build', success=False)
  )

  yield (
      api.test('failed_upload') +
      api.runtime(is_luci=True, is_experimental=False) +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build') +
      api.override_step_data(
          'build.git cl issue',
          api.json.output({'issue': None, 'issue_url': None}))
  )

  yield (
      api.test('repo_data_trivial_cq') +
      api.runtime(is_luci=True, is_experimental=False) +
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
      api.runtime(is_luci=True, is_experimental=False) +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.recipe_cfg('build') +
      api.recipe_autoroller.repo_data(
          'build', trivial=True, status='commit',
          timestamp='2016-02-01T01:23:45') +
      api.time.seed(1454371200)
  )

  yield (
      api.test('repo_data_trivial_open') +
      api.runtime(is_luci=True, is_experimental=False) +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.repo_data(
          'build', trivial=True, status='open',
          timestamp='2016-02-01T01:23:45') +
      api.recipe_autoroller.roll_data('build') +
      api.time.seed(1451606400) +
      api.post_process(MustRun, 'build.git cl set-close')
  )

  yield (
      api.test('repo_data_trivial_closed') +
      api.runtime(is_luci=True, is_experimental=False) +
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
      api.runtime(is_luci=True, is_experimental=False) +
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
      api.runtime(is_luci=True, is_experimental=False) +
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
      api.runtime(is_luci=True, is_experimental=False) +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data('build', trivial_commit=False)
  )

  yield (
      api.test('repo_disabled') +
      api.runtime(is_luci=True, is_experimental=False) +
      api.properties(projects=['build']) +
      api.luci_config.get_projects(['build']) +
      api.recipe_autoroller.roll_data(
        'build', disable_reason='I am a water buffalo.')
  )
