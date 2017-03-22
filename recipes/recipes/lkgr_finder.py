# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property
from recipe_engine.types import freeze

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]


PROPERTIES = {
  'buildername': Property(kind=str),
}


BUILDERS = freeze({
  'V8 lkgr finder': {
    'project': 'v8',
    'allowed_lag': 4,
  },
})


def RunSteps(api, buildername):
  botconfig = BUILDERS[buildername]
  api.gclient.set_config('infra')
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()

  # TODO(machenbach): Create and upload lkgr-status html file.
  args = [
    'infra.services.lkgr_finder',
    '--project=%s' % botconfig['project'],
    # TODO(machenbach,friedman): Add shared creds for status apps.
    '--password-file=/creds/gatekeeper/%s_status_password' %
        botconfig['project'],
    '--verbose',
    '--email-errors',
    '--post',
  ]

  if botconfig.get('allowed_lag') is not None:
    args.append('--allowed-lag=%d' % botconfig['allowed_lag'])

  api.python(
      'calculate %s lkgr' % botconfig['project'],
      api.path['checkout'].join('run.py'),
      args,
  )


def GenTests(api):
  for buildername, botconfig in BUILDERS.iteritems():
    yield (
        api.test(botconfig['project']) +
        api.properties.generic(
            buildername=buildername,
        )
    )
