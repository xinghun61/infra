# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property
from recipe_engine.types import freeze

DEPS = [
  'build/gitiles',
  'build/url',
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
    'repo': 'https://chromium.googlesource.com/v8/v8',
    'ref': 'refs/heads/lkgr',
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

  # Check if somebody manually pushed a newer lkgr to the lkgr ref.
  # In this case manually override the lkgr in the app. This can be used
  # to manually advance the lkgr when backing services are down.
  if botconfig.get('ref'):
    lkgr_from_ref = api.gitiles.commit_log(
        botconfig['repo'], botconfig['ref'],
        step_name='lkgr from ref')['commit']
    lkgr_from_app = api.url.fetch(
        'https://%s-status.appspot.com/lkgr' % botconfig['project'],
        step_name='lkgr from app'
    )
    commits, _ = api.gitiles.log(
        botconfig['repo'], '%s..%s' % (lkgr_from_app, lkgr_from_ref),
        step_name='check lkgr override')
    if commits:
      args.append('--manual=%s' % lkgr_from_ref)

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
  def lkgr_test_data():
    return (
        api.step_data(
            'lkgr from ref',
            api.gitiles.make_commit_test_data('deadbeef1', 'Commit1'),
        ) +
        api.step_data(
            'lkgr from app',
            api.raw_io.stream_output('deadbeef2'),
        )
    )

  for buildername, botconfig in BUILDERS.iteritems():
    yield (
        api.test(botconfig['project']) +
        api.properties.generic(
            buildername=buildername,
        ) +
        lkgr_test_data() +
        api.step_data(
            'check lkgr override',
            api.gitiles.make_log_test_data('A', n=0),
        )
    )
    yield (
        api.test(botconfig['project'] + '_manual') +
        api.properties.generic(
            buildername=buildername,
            revision='deadbeef',
        ) +
        lkgr_test_data() +
        api.step_data(
            'check lkgr override',
            api.gitiles.make_log_test_data('A'),
        )
    )
