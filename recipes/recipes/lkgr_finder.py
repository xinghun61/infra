# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property
from recipe_engine.types import freeze

DEPS = [
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/gsutil',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
  'recipe_engine/step',
]


PROPERTIES = {
  'buildername': Property(kind=str),
}


BUILDERS = freeze({
  'V8 lkgr finder': {
    'project': 'v8',
    'allowed_lag': 4,
    'lkgr_status_gs_path': 'chromium-v8/lkgr-status',
  },
})


def RunSteps(api, buildername):
  botconfig = BUILDERS[buildername]
  api.gclient.set_config('infra')
  api.gclient.c.revisions['infra'] = 'HEAD'
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()

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

  # Forcing builds with a revision property set is used to manually override
  # the lkgr.
  if api.properties.get('revision'):
    args.append('--manual=%s' % api.properties['revision'])

  if botconfig.get('allowed_lag') is not None:
    args.append('--allowed-lag=%d' % botconfig['allowed_lag'])

  kwargs = {}
  if botconfig.get('lkgr_status_gs_path'):
    args += ['--html', api.raw_io.output_text()]
    kwargs['step_test_data'] = lambda: api.raw_io.test_api.output_text(
        '<html>lkgr-status</html>')

  step_result = api.python(
      'calculate %s lkgr' % botconfig['project'],
      api.path['checkout'].join('run.py'),
      args,
      **kwargs
  )

  if botconfig.get('lkgr_status_gs_path'):
    api.gsutil.upload(
      api.raw_io.input_text(step_result.raw_io.output_text),
      botconfig['lkgr_status_gs_path'],
      '%s-lkgr-status.html' % botconfig['project'],
      args=['-a', 'public-read'],
      metadata={'Content-Type': 'text/html'},
    )


def GenTests(api):
  for buildername, botconfig in BUILDERS.iteritems():
    yield (
        api.test(botconfig['project']) +
        api.properties.generic(
            buildername=buildername,
        )
    )
    yield (
        api.test(botconfig['project'] + '_manual') +
        api.properties.generic(
            buildername=buildername,
            revision='deadbeef',
        )
    )
