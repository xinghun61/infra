# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Rolls recipes.cfg dependencies for public projects."""

DEPS = [
  'recipe_autoroller',

  'recipe_engine/json',
  'recipe_engine/properties',
  'recipe_engine/runtime',
  'recipe_engine/time',
]

from recipe_engine import recipe_api
from recipe_engine.post_process import MustRun


PROPERTIES = {
  'projects': recipe_api.Property(),
}


def RunSteps(api, projects):
  api.recipe_autoroller.roll_projects(projects)


def GenTests(api):
  def test(name):
    return (
        api.test(name) +
        api.runtime(is_luci=True, is_experimental=False) +
        api.properties(projects=[
          ('build', 'https://example.com/build.git'),
        ])
    )

  yield (
      test('basic') +
      api.recipe_autoroller.roll_data('build')
  )

  yield (
      test('nontrivial') +
      api.recipe_autoroller.roll_data('build', trivial=False)
  )

  yield (
      test('empty') +
      api.recipe_autoroller.roll_data('build', empty=True)
  )

  yield (
      test('failure') +
      api.recipe_autoroller.roll_data('build', success=False)
  )

  yield (
      test('failed_upload') +
      api.recipe_autoroller.roll_data('build') +
      api.override_step_data(
          'build.git cl issue',
          api.json.output({'issue': None, 'issue_url': None}))
  )

  yield (
      test('repo_data_trivial_cq') +
      api.recipe_autoroller.recipe_cfg('build') +
      api.recipe_autoroller.repo_data(
          'build', trivial=True, status='commit',
          timestamp='2016-02-01T01:23:45') +
      api.time.seed(1451606400)
  )

  yield (
      test('repo_data_trivial_cq_stale') +
      api.recipe_autoroller.recipe_cfg('build') +
      api.recipe_autoroller.repo_data(
          'build', trivial=True, status='commit',
          timestamp='2016-02-01T01:23:45') +
      api.time.seed(1454371200)
  )

  yield (
      test('repo_data_trivial_open') +
      api.recipe_autoroller.repo_data(
          'build', trivial=True, status='open',
          timestamp='2016-02-01T01:23:45') +
      api.recipe_autoroller.roll_data('build') +
      api.time.seed(1451606400) +
      api.post_process(MustRun, 'build.git cl set-close')
  )

  yield (
      test('repo_data_trivial_closed') +
      api.recipe_autoroller.repo_data(
          'build', trivial=True, status='closed',
          timestamp='2016-02-01T01:23:45') +
      api.recipe_autoroller.roll_data('build') +
      api.time.seed(1451606400)
  )

  yield (
      test('repo_data_nontrivial_open') +
      api.recipe_autoroller.recipe_cfg('build') +
      api.recipe_autoroller.repo_data(
          'build', trivial=False, status='waiting',
          timestamp='2016-02-01T01:23:45') +
      api.time.seed(1451606400)
  )

  yield (
      test('repo_data_nontrivial_open_stale') +
      api.recipe_autoroller.recipe_cfg('build') +
      api.recipe_autoroller.repo_data(
          'build', trivial=False, status='waiting',
          timestamp='2016-02-01T01:23:45') +
      api.time.seed(1454371200)
  )

  yield (
      test('trivial_custom_tbr_no_dryrun') +
      api.recipe_autoroller.roll_data('build', trivial_commit=False)
  )

  yield (
      test('repo_disabled') +
      api.recipe_autoroller.roll_data(
        'build', disable_reason='I am a water buffalo.')
  )

  # The recipe shouldn't crash if the autoroller options are not specified.
  yield (
      test('trivial_no_autoroll_options') +
      api.recipe_autoroller.roll_data(
          'build', trivial=True, include_autoroll_options=False)
  )

  yield (
      test('nontrivial_no_autoroll_options') +
      api.recipe_autoroller.roll_data(
          'build', trivial=False, include_autoroll_options=False)
  )
