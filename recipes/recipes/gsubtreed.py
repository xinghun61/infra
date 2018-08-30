# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs git subtree daemon (gsubtreed) against Chromium src repo.

Intended to be called periodically (see CYCLE_TIME_SEC). Runs several iteration
of the daemon and then quits so that recipe has a chance to resync the source
code.
"""

import urlparse

DEPS = [
  'depot_tools/gclient',
  'recipe_engine/context',
  'recipe_engine/json',
  'recipe_engine/path',
  'recipe_engine/properties',
  'recipe_engine/python',
  'recipe_engine/step',
]


# Repository to operate upon.
MAIN_REPO = 'https://chromium.googlesource.com/chromium/src'

# How long to run gsubtreed. Should be in sync with buildbot scheduler period.
CYCLE_TIME_SEC = 10 * 60

# How many consecutive errors are tolerated before gsubtreed quits with error.
MAX_ERROR_COUNT = 5


def RunSteps(api):
  # Checkout infra/infra solution.
  api.gclient.set_config('infra')
  api.gclient.c.solutions[0].revision = 'origin/deployed'
  api.gclient.checkout(timeout=10*60)
  api.gclient.runhooks()

  env = {}
  repo = api.properties.get('target_repo', MAIN_REPO)
  # github.com apparently has a hard time with our user agents.
  if urlparse.urlparse(repo).hostname.endswith('github.com'):
    env['GIT_USER_AGENT'] = None

  # Run the daemon for CYCLE_TIME_SEC seconds.
  # TODO(iannucci): Make infra.run a module
  try:
    with api.context(env=env):
      api.python(
          'gsubtreed',
          api.path['checkout'].join('run.py'),
          [
            'infra.services.gsubtreed',
            '--verbose',
            '--duration', str(CYCLE_TIME_SEC),
            '--max_errors', str(MAX_ERROR_COUNT),
            '--repo_dir',
            api.path['cache'].join('builder', 'gsubtreed-work-dir'),
            '--json_output', api.json.output(add_json_log=False),
            repo,
          ])
  finally:
    step_result = api.step.active_result
    # Add a list of generates commits to the build page.
    if step_result.json.output:
      path_counts = step_result.json.output['summary']
      step_result.presentation.step_text = '</br></br>'
      step_result.presentation.step_text += '</br>'.join(
        '%s: %s' % (path, num) for path, num in path_counts.iteritems() if num
      )
      total = sum(path_counts.values())
      step_result.presentation.step_summary_text = 'commits: %d' % total


def GenTests(api):
  json_output = {
    'error_count': 2,
    'summary': {
      'some/path': 5,
      'some': 10,
      'other': 0,
    }
  }

  props = lambda: api.properties(mastername='fake', buildername='fake',
                                 bot_id='fake')

  yield (
    api.test('success') +
    api.step_data('gsubtreed', api.json.output(json_output), retcode=0) +
    props()
  )
  yield (
    api.test('failure') +
    api.step_data('gsubtreed', api.json.output(json_output), retcode=1) +
    props()
  )
  yield (
    api.test('alt') +
    api.properties(target_repo='https://host.googlesource.com/my/repo') +
    api.step_data('gsubtreed', api.json.output(json_output), retcode=0) +
    props()
  )
  yield (
    api.test('github_env_var') +
    api.properties(target_repo='https://github.com/sweet/repo') +
    api.step_data('gsubtreed', api.json.output(json_output), retcode=0) +
    props()
  )
