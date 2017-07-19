# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This recipe builds and packages third party software, such as Git."""

from recipe_engine.recipe_api import Property


DEPS = [
  'depot_tools/cipd',
  'depot_tools/gitiles',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/step',
  'third_party_packages',
]

PROPERTIES = {
  'dry_run': Property(default=True, kind=bool),
}


def RunSteps(api, dry_run):
  api.third_party_packages.dry_run = dry_run
  if not dry_run:
    api.cipd.set_service_account_credentials(
        api.cipd.default_bot_service_account_credentials)

  with api.step.defer_results():
    with api.step.nest('python'):
      api.third_party_packages.python.package()
    with api.step.nest('git'):
      api.third_party_packages.git.package()
    with api.step.nest('gcloud'):
      api.third_party_packages.gcloud.package()


def GenTests(api):
  yield (
      api.test('basic') +
      api.platform.name('linux') +
      api.platform.bits(64) +
      api.properties(dry_run=False) +
      api.step_data('git.refs',
        api.gitiles.make_refs_test_data('refs/tags/v2.12.2.2')) +
      api.step_data('python.refs',
        api.gitiles.make_refs_test_data('refs/tags/v2.1.2'))
  )

  yield (
      api.test('dry_run') +
      api.platform.name('linux') +
      api.platform.bits(64) +
      api.step_data('git.refs',
        api.gitiles.make_refs_test_data('refs/tags/v2.12.2.2')) +
      api.step_data('python.refs',
        api.gitiles.make_refs_test_data('refs/tags/v2.1.2'))
  )
