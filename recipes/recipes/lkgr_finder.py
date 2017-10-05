# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property
from recipe_engine.types import freeze

DEPS = [
  'build/v8',
  'build/webrtc',
  'build/chromium_checkout',
  'depot_tools/bot_update',
  'depot_tools/gclient',
  'depot_tools/git',
  'depot_tools/gitiles',
  'depot_tools/gsutil',
  'recipe_engine/context',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/raw_io',
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
    'gclient_config': 'v8',
    'checkout_dir': 'v8',
  },
  'WebRTC lkgr finder': {
    'project': 'webrtc',
    'repo': 'https://webrtc.googlesource.com/src',
    'ref': 'refs/heads/lkgr',
    'gclient_config': 'webrtc',
    'checkout_dir': 'src',
  }
  # When adding a new builder, please make sure to add dep containing relevant
  # gclient_config into DEPS list above.
})


def RunSteps(api, buildername):
  botconfig = BUILDERS[buildername]
  api.gclient.set_config('infra')
  api.gclient.c.revisions['infra'] = 'HEAD'
  api.gclient.apply_config(botconfig['gclient_config'])

  # Projects can define revision mappings that conflict with infra revision
  # mapping, so we overide them here to only map infra's revision so that it
  # shows up on the buildbot page.
  api.gclient.c.got_revision_mapping = {}
  api.gclient.c.got_revision_reverse_mapping = {'got_revision': 'infra'}

  checkout_dir = api.chromium_checkout.get_checkout_dir({})
  with api.context(cwd=api.context.cwd or checkout_dir):
    api.bot_update.ensure_checkout()

  api.gclient.runhooks()

  repo, ref = botconfig['repo'], botconfig['ref']
  current_lkgr = api.gitiles.commit_log(
      repo, ref, step_name='read lkgr from ref')['commit']

  args = [
    'infra.services.lkgr_finder',
    '--project=%s' % botconfig['project'],
    # TODO(machenbach,friedman): Add shared creds for status apps.
    '--password-file=/creds/gatekeeper/%s_status_password' %
        botconfig['project'],
    '--verbose',
    '--email-errors',
    # TODO(sergiyb): Remove this after we have verified that pushing to ref
    # works and removed LKGR pushing mechanism from the
    # auto_roll_release_process recipe.
    '--post',
    '--read-from-file', api.raw_io.input_text(current_lkgr),
    '--write-to-file', api.raw_io.output_text(name='lkgr_hash'),
  ]
  step_test_data = api.raw_io.test_api.output_text(
      'deadbeef' * 5, name='lkgr_hash')

  if botconfig.get('allowed_lag') is not None:
    args.append('--allowed-lag=%d' % botconfig['allowed_lag'])

  if botconfig.get('lkgr_status_gs_path'):
    args += ['--html', api.raw_io.output_text(name='html')]
    step_test_data += api.raw_io.test_api.output_text(
        '<html>lkgr</html>', name='html')

  step_result = api.python(
      'calculate %s lkgr' % botconfig['project'],
      api.path['start_dir'].join('infra', 'run.py'),
      args,
      step_test_data=lambda: step_test_data
  )

  if botconfig.get('lkgr_status_gs_path'):
    api.gsutil.upload(
      api.raw_io.input_text(step_result.raw_io.output_texts['html']),
      botconfig['lkgr_status_gs_path'],
      '%s-lkgr-status.html' % botconfig['project'],
      args=['-a', 'public-read'],
      metadata={'Content-Type': 'text/html'},
    )

  new_lkgr = step_result.raw_io.output_texts['lkgr_hash']
  if new_lkgr and new_lkgr != current_lkgr:
    with api.context(cwd=api.path['start_dir'].join(botconfig['checkout_dir'])):
      api.git('push', repo, '%s:%s' % (new_lkgr, ref), name='push lkgr to ref')


def GenTests(api):
  for buildername, botconfig in BUILDERS.iteritems():
    yield (
        api.test(botconfig['project']) +
        api.properties.generic(buildername=buildername) +
        api.properties(path_config='kitchen') +
        api.step_data(
            'read lkgr from ref',
            api.gitiles.make_commit_test_data('deadbeef1', 'Commit1'),
        )
    )
