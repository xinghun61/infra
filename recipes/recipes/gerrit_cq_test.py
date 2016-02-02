# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/properties',
]

REPO = 'https://chromium.googlesource.com/playground/gerrit-cq/normal'


def RunSteps(api):
  api.gclient.set_config('gerrit_test_cq_normal')
  api.bot_update.ensure_checkout(patch=True, force=True);


def GenTests(api):
  gerrit_kwargs={
    'event.change.id':
      'playground/gerrit-cq/normal'
      '~master~Iff9c127b16841bc27728304a5ba2caff49ff11b5',
    'event.change.number': 322360,
    'event.change.url': 'https://chromium-review.googlesource.com/#/c/322360',
    'event.patchSet.ref': 'refs/changes/60/322360/2',
  }
  yield (
    api.test('try') +
    api.properties.generic(
        buildername='gerrit-test-cq-normal',
        buildnumber=123,
        mastername='tryserver.infra',
        repository=REPO,
        **gerrit_kwargs
    )
  )
