# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]

PROPERTIES = {
  'project': Property(
      default=None, kind=str, help='Project to calculate lkgr for.'),
  'allowed_lag': Property(
      default=None, kind=int,
      help='How many hours to allow since an LKGR update '
           'before it\'s considered out-of-date.'),
}


def RunSteps(api, project, allowed_lag):
  assert project
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()

  # TODO(machenbach): Create and upload lkgr-status html file.
  args = [
    'infra.services.lkgr_finder',
    '--project=%s' % project,
    # TODO(machenbach,friedman): Add shared creds for status apps.
    '--password-file=/creds/gatekeeper/%s_status_password' % project,
    '--verbose',
    '--email-errors',
    '--post',
  ]

  if allowed_lag is not None:
    args.append('--allowed-lag=%d' % allowed_lag)

  api.python(
      'calculate %s lkgr' % project,
      api.path['checkout'].join('run.py'),
      args,
  )


def GenTests(api):
    yield (
        api.test('v8') +
        api.properties.generic(
            project='v8',
            allowed_lag=4,
        )
    )
